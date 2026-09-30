"""
alpha_core/monitoring/benchmark_exporter.py
Continuous Live Tournament & Benchmark Telemetry Exporter.

Reads /tmp/alphabrain_h2h_results.json, computes multi-dimensional
speedup ratios, registers Prometheus metrics, and exposes
/api/v1/benchmarks/live FastAPI router.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("alphabrain.monitoring.benchmark_exporter")

DEFAULT_RESULTS_PATH = Path("/tmp/alphabrain_h2h_results.json")


@dataclass
class ContestantResult:
    """Single contestant's result for one problem."""
    tests_passed: int
    tests_total: int
    wall_clock_seconds: float
    total_tokens: int
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cost_usd: float
    reasoning_turns: int
    tool_calls: int
    code_edits: int
    loc_added: int
    loc_deleted: int
    clippy_warnings: int
    clippy_errors: int
    compiler_pass: bool
    runtime_pass: bool

    @property
    def pass_rate(self) -> float:
        if self.tests_total == 0:
            return 0.0
        return self.tests_passed / self.tests_total

    @property
    def fully_passed(self) -> bool:
        return self.compiler_pass and self.runtime_pass and self.pass_rate == 1.0


@dataclass
class SpeedupRatio:
    """Multi-dimensional speedup ratios comparing two contestants."""
    wall_clock_speedup: float    # > 1.0 means first contestant is faster
    token_efficiency: float      # > 1.0 means first contestant uses fewer tokens
    cost_efficiency: float       # > 1.0 means first contestant is cheaper
    turn_efficiency: float       # > 1.0 means first contestant uses fewer turns
    tool_call_efficiency: float  # > 1.0 means first contestant uses fewer tool calls
    code_edit_efficiency: float  # > 1.0 means first contestant makes fewer edits

    def to_dict(self) -> dict[str, float]:
        return {
            "wall_clock_speedup": round(self.wall_clock_speedup, 3),
            "token_efficiency": round(self.token_efficiency, 3),
            "cost_efficiency": round(self.cost_efficiency, 3),
            "turn_efficiency": round(self.turn_efficiency, 3),
            "tool_call_efficiency": round(self.tool_call_efficiency, 3),
            "code_edit_efficiency": round(self.code_edit_efficiency, 3),
        }


@dataclass
class ProblemSummary:
    """Summary of a single problem's benchmark results."""
    problem_id: str
    language: str
    results: dict[str, ContestantResult]
    speedup: SpeedupRatio | None = None
    winner: str | None = None


@dataclass
class TournamentSummary:
    """Aggregate tournament summary across all problems."""
    tournament_id: str
    generated_at: str
    contestants: list[str]
    problems: list[ProblemSummary]
    aggregate_wins: dict[str, int] = field(default_factory=dict)
    aggregate_wall_clock: dict[str, float] = field(default_factory=dict)
    aggregate_tokens: dict[str, int] = field(default_factory=dict)
    aggregate_cost: dict[str, float] = field(default_factory=dict)
    aggregate_speedup: SpeedupRatio | None = None
    loaded_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tournament_id": self.tournament_id,
            "generated_at": self.generated_at,
            "contestants": self.contestants,
            "total_problems": len(self.problems),
            "aggregate_wins": self.aggregate_wins,
            "aggregate_wall_clock": self.aggregate_wall_clock,
            "aggregate_tokens": self.aggregate_tokens,
            "aggregate_cost": {k: round(v, 6) for k, v in self.aggregate_cost.items()},
            "aggregate_speedup": self.aggregate_speedup.to_dict() if self.aggregate_speedup else None,
            "problems": [
                {
                    "problem_id": p.problem_id,
                    "language": p.language,
                    "winner": p.winner,
                    "speedup": p.speedup.to_dict() if p.speedup else None,
                    "results": {
                        k: {
                            "tests": f"{v.tests_passed}/{v.tests_total}",
                            "pass_rate": round(v.pass_rate, 3),
                            "wall_clock_seconds": v.wall_clock_seconds,
                            "total_tokens": v.total_tokens,
                            "cost_usd": round(v.cost_usd, 6),
                            "reasoning_turns": v.reasoning_turns,
                            "tool_calls": v.tool_calls,
                            "compiler_pass": v.compiler_pass,
                            "runtime_pass": v.runtime_pass,
                        }
                        for k, v in p.results.items()
                    },
                }
                for p in self.problems
            ],
            "loaded_at_epoch": self.loaded_at,
        }


class BenchmarkTelemetryExporter:
    """Reads benchmark results, computes speedup ratios, exposes metrics.

    Usage:
        exporter = BenchmarkTelemetryExporter()
        summary = exporter.load_and_compute()
        router = exporter.create_fastapi_router()
    """

    def __init__(
        self,
        results_path: Path = DEFAULT_RESULTS_PATH,
        primary_contestant: str = "etta",
    ):
        self.results_path = Path(results_path)
        self.primary_contestant = primary_contestant
        self._summary: TournamentSummary | None = None
        self._prometheus_metrics: dict[str, Any] = {}

    @property
    def summary(self) -> TournamentSummary | None:
        return self._summary

    @staticmethod
    def _safe_divide(numerator: float, denominator: float) -> float:
        """Safely divides numerator by denominator with division-by-zero protection.

        If denominator == 0 and numerator > 0 -> float('inf')
        If both == 0 -> 1.0
        """
        if denominator == 0.0:
            if numerator > 0.0:
                return float("inf")
            return 1.0
        return float(numerator / denominator)

    def _compute_speedup(
        self, a: ContestantResult, b: ContestantResult
    ) -> SpeedupRatio:
        """Compute speedup ratios. a is primary, b is opponent.

        Ratio > 1.0 means a is better (faster, fewer tokens, lower cost, etc.).
        Division by zero protection: if denominator is 0, ratio is float('inf') if
        numerator > 0, else 1.0.
        """
        return SpeedupRatio(
            wall_clock_speedup=self._safe_divide(b.wall_clock_seconds, a.wall_clock_seconds),
            token_efficiency=self._safe_divide(float(b.total_tokens), float(a.total_tokens)),
            cost_efficiency=self._safe_divide(b.cost_usd, a.cost_usd),
            turn_efficiency=self._safe_divide(float(b.reasoning_turns), float(a.reasoning_turns)),
            tool_call_efficiency=self._safe_divide(float(b.tool_calls), float(a.tool_calls)),
            code_edit_efficiency=self._safe_divide(float(b.code_edits), float(a.code_edits)),
        )

    def _determine_winner(self, problem: ProblemSummary) -> str | None:
        """Determine winner: first by pass_rate, then by wall_clock_seconds.

        If problem has != 2 contestants, winner is None.
        If contestants tie on both pass_rate and wall_clock_seconds, returns None.
        """
        if len(problem.results) != 2:
            return None

        contestants = list(problem.results.keys())
        c1, c2 = contestants[0], contestants[1]
        r1, r2 = problem.results[c1], problem.results[c2]

        if r1.pass_rate > r2.pass_rate:
            return c1
        if r2.pass_rate > r1.pass_rate:
            return c2

        # Tie on pass_rate -> lower wall_clock_seconds wins
        if r1.wall_clock_seconds < r2.wall_clock_seconds:
            return c1
        if r2.wall_clock_seconds < r1.wall_clock_seconds:
            return c2

        return None

    def _compute_aggregates(self, summary: TournamentSummary) -> None:
        """Compute aggregate wins, total wall clock, total tokens, total cost."""
        summary.aggregate_wins = dict.fromkeys(summary.contestants, 0)
        summary.aggregate_wall_clock = dict.fromkeys(summary.contestants, 0.0)
        summary.aggregate_tokens = dict.fromkeys(summary.contestants, 0)
        summary.aggregate_cost = dict.fromkeys(summary.contestants, 0.0)

        aggregate_turns: dict[str, int] = dict.fromkeys(summary.contestants, 0)
        aggregate_tool_calls: dict[str, int] = dict.fromkeys(summary.contestants, 0)
        aggregate_code_edits: dict[str, int] = dict.fromkeys(summary.contestants, 0)

        for prob in summary.problems:
            if prob.winner and prob.winner in summary.aggregate_wins:
                summary.aggregate_wins[prob.winner] += 1
            for c, res in prob.results.items():
                if c not in summary.aggregate_wall_clock:
                    summary.aggregate_wins[c] = 0
                    summary.aggregate_wall_clock[c] = 0.0
                    summary.aggregate_tokens[c] = 0
                    summary.aggregate_cost[c] = 0.0
                    aggregate_turns[c] = 0
                    aggregate_tool_calls[c] = 0
                    aggregate_code_edits[c] = 0

                summary.aggregate_wall_clock[c] += res.wall_clock_seconds
                summary.aggregate_tokens[c] += res.total_tokens
                summary.aggregate_cost[c] += res.cost_usd
                aggregate_turns[c] += res.reasoning_turns
                aggregate_tool_calls[c] += res.tool_calls
                aggregate_code_edits[c] += res.code_edits

        # Compute aggregate_speedup if there are exactly 2 contestants
        if len(summary.contestants) == 2:
            primary = (
                self.primary_contestant
                if self.primary_contestant in summary.contestants
                else summary.contestants[0]
            )
            opponents = [c for c in summary.contestants if c != primary]
            if opponents:
                opponent = opponents[0]
                summary.aggregate_speedup = SpeedupRatio(
                    wall_clock_speedup=self._safe_divide(
                        summary.aggregate_wall_clock[opponent],
                        summary.aggregate_wall_clock[primary],
                    ),
                    token_efficiency=self._safe_divide(
                        float(summary.aggregate_tokens[opponent]),
                        float(summary.aggregate_tokens[primary]),
                    ),
                    cost_efficiency=self._safe_divide(
                        summary.aggregate_cost[opponent],
                        summary.aggregate_cost[primary],
                    ),
                    turn_efficiency=self._safe_divide(
                        float(aggregate_turns[opponent]),
                        float(aggregate_turns[primary]),
                    ),
                    tool_call_efficiency=self._safe_divide(
                        float(aggregate_tool_calls[opponent]),
                        float(aggregate_tool_calls[primary]),
                    ),
                    code_edit_efficiency=self._safe_divide(
                        float(aggregate_code_edits[opponent]),
                        float(aggregate_code_edits[primary]),
                    ),
                )

    def _parse_results(self, data: dict[str, Any]) -> TournamentSummary:
        """Parse raw JSON into typed TournamentSummary."""
        for key in ("tournament_id", "generated_at", "contestants", "problems"):
            if key not in data:
                msg = f"Missing required key in benchmark results: '{key}'"
                logger.error(msg)
                raise KeyError(msg)

        problem_summaries: list[ProblemSummary] = []
        for prob_data in data["problems"]:
            if "problem_id" not in prob_data or "results" not in prob_data:
                msg = "Each problem must contain 'problem_id' and 'results'"
                logger.error(msg)
                raise KeyError(msg)

            problem_id = str(prob_data["problem_id"])
            language = str(prob_data.get("language", "unknown"))

            parsed_results: dict[str, ContestantResult] = {}
            for contestant_name, res_dict in prob_data["results"].items():
                parsed_results[contestant_name] = ContestantResult(
                    tests_passed=int(res_dict.get("tests_passed", 0)),
                    tests_total=int(res_dict.get("tests_total", 0)),
                    wall_clock_seconds=float(res_dict.get("wall_clock_seconds", 0.0)),
                    total_tokens=int(res_dict.get("total_tokens", 0)),
                    input_tokens=int(res_dict.get("input_tokens", 0)),
                    output_tokens=int(res_dict.get("output_tokens", 0)),
                    thinking_tokens=int(res_dict.get("thinking_tokens", 0)),
                    cost_usd=float(res_dict.get("cost_usd", 0.0)),
                    reasoning_turns=int(res_dict.get("reasoning_turns", 0)),
                    tool_calls=int(res_dict.get("tool_calls", 0)),
                    code_edits=int(res_dict.get("code_edits", 0)),
                    loc_added=int(res_dict.get("loc_added", 0)),
                    loc_deleted=int(res_dict.get("loc_deleted", 0)),
                    clippy_warnings=int(res_dict.get("clippy_warnings", 0)),
                    clippy_errors=int(res_dict.get("clippy_errors", 0)),
                    compiler_pass=bool(res_dict.get("compiler_pass", False)),
                    runtime_pass=bool(res_dict.get("runtime_pass", False)),
                )

            problem_summaries.append(
                ProblemSummary(
                    problem_id=problem_id,
                    language=language,
                    results=parsed_results,
                )
            )

        return TournamentSummary(
            tournament_id=str(data["tournament_id"]),
            generated_at=str(data["generated_at"]),
            contestants=list(data["contestants"]),
            problems=problem_summaries,
            loaded_at=time.time(),
        )

    def load_and_compute(self) -> TournamentSummary:
        """Load results JSON and compute all speedup ratios."""
        p = Path(self.results_path)
        if not p.is_file():
            logger.error("Results file does not exist: %s", p)
            raise FileNotFoundError(f"Results file does not exist: {p}")

        try:
            raw_text = p.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to decode JSON from %s: %s", p, exc)
            raise

        summary = self._parse_results(data)

        # Compute speedup and winner for each problem
        for prob in summary.problems:
            if len(prob.results) == 2:
                primary = (
                    self.primary_contestant
                    if self.primary_contestant in prob.results
                    else next(iter(prob.results.keys()))
                )
                opponents = [c for c in prob.results if c != primary]
                if opponents:
                    opponent = opponents[0]
                    prob.speedup = self._compute_speedup(
                        prob.results[primary], prob.results[opponent]
                    )
                prob.winner = self._determine_winner(prob)
            else:
                prob.speedup = None
                prob.winner = None

        self._compute_aggregates(summary)
        self._summary = summary
        return summary

    def get_prometheus_text(self) -> str:
        """Generate Prometheus text exposition format string.

        Does NOT require prometheus_client — generates text manually.
        Format: # HELP ... \\n# TYPE ... \\n metric_name{labels} value
        """
        if self._summary is None:
            if Path(self.results_path).is_file():
                self.load_and_compute()
            else:
                return ""

        summary = self._summary
        if summary is None:
            return ""

        lines: list[str] = []

        def sanitize(val: Any) -> str:
            return str(val).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

        # 1. alphabrain_benchmark_wall_clock_seconds
        lines.append(
            "# HELP alphabrain_benchmark_wall_clock_seconds Problem execution wall-clock time in seconds"
        )
        lines.append("# TYPE alphabrain_benchmark_wall_clock_seconds gauge")
        for p in summary.problems:
            for contestant, r in p.results.items():
                lines.append(
                    f'alphabrain_benchmark_wall_clock_seconds{{contestant="{sanitize(contestant)}",problem_id="{sanitize(p.problem_id)}"}} {r.wall_clock_seconds}'
                )

        # 2. alphabrain_benchmark_tokens_total
        lines.append("# HELP alphabrain_benchmark_tokens_total Total tokens consumed for problem")
        lines.append("# TYPE alphabrain_benchmark_tokens_total gauge")
        for p in summary.problems:
            for contestant, r in p.results.items():
                lines.append(
                    f'alphabrain_benchmark_tokens_total{{contestant="{sanitize(contestant)}",problem_id="{sanitize(p.problem_id)}"}} {r.total_tokens}'
                )

        # 3. alphabrain_benchmark_cost_usd
        lines.append("# HELP alphabrain_benchmark_cost_usd Total dollar cost in USD for problem")
        lines.append("# TYPE alphabrain_benchmark_cost_usd gauge")
        for p in summary.problems:
            for contestant, r in p.results.items():
                lines.append(
                    f'alphabrain_benchmark_cost_usd{{contestant="{sanitize(contestant)}",problem_id="{sanitize(p.problem_id)}"}} {r.cost_usd}'
                )

        # 4. alphabrain_benchmark_tests_passed
        lines.append("# HELP alphabrain_benchmark_tests_passed Number of tests passed for problem")
        lines.append("# TYPE alphabrain_benchmark_tests_passed gauge")
        for p in summary.problems:
            for contestant, r in p.results.items():
                lines.append(
                    f'alphabrain_benchmark_tests_passed{{contestant="{sanitize(contestant)}",problem_id="{sanitize(p.problem_id)}"}} {r.tests_passed}'
                )

        # 5. alphabrain_benchmark_speedup_ratio
        if summary.aggregate_speedup:
            lines.append(
                "# HELP alphabrain_benchmark_speedup_ratio Aggregate speedup ratio of primary contestant over opponent"
            )
            lines.append("# TYPE alphabrain_benchmark_speedup_ratio gauge")
            for dim, val in summary.aggregate_speedup.to_dict().items():
                lines.append(
                    f'alphabrain_benchmark_speedup_ratio{{dimension="{sanitize(dim)}"}} {val}'
                )

        # 6. alphabrain_benchmark_wins_total
        lines.append(
            "# HELP alphabrain_benchmark_wins_total Total tournament problem wins per contestant"
        )
        lines.append("# TYPE alphabrain_benchmark_wins_total counter")
        for contestant, wins in summary.aggregate_wins.items():
            lines.append(
                f'alphabrain_benchmark_wins_total{{contestant="{sanitize(contestant)}"}} {wins}'
            )

        return "\n".join(lines) + "\n"

    def register_prometheus_metrics(self) -> dict[str, Any]:
        """Register Prometheus gauges for each metric dimension.

        Metrics registered:
        - alphabrain_benchmark_wall_clock_seconds{contestant, problem_id}
        - alphabrain_benchmark_tokens_total{contestant, problem_id}
        - alphabrain_benchmark_cost_usd{contestant, problem_id}
        - alphabrain_benchmark_tests_passed{contestant, problem_id}
        - alphabrain_benchmark_speedup_ratio{dimension}  (wall_clock, tokens, cost)
        - alphabrain_benchmark_wins_total{contestant}

        Returns dict of metric name -> prometheus metric object.
        Note: Uses try/except ImportError for prometheus_client — if not installed,
        logs warning and returns empty dict (graceful degradation).
        """
        try:
            from prometheus_client import Counter, Gauge
        except ImportError:
            logger.warning(
                "prometheus_client is not installed; returning empty metrics dictionary."
            )
            return {}

        try:
            if not self._prometheus_metrics:
                self._prometheus_metrics["alphabrain_benchmark_wall_clock_seconds"] = Gauge(
                    "alphabrain_benchmark_wall_clock_seconds",
                    "Problem execution wall-clock time in seconds",
                    ["contestant", "problem_id"],
                )
                self._prometheus_metrics["alphabrain_benchmark_tokens_total"] = Gauge(
                    "alphabrain_benchmark_tokens_total",
                    "Total tokens consumed for problem",
                    ["contestant", "problem_id"],
                )
                self._prometheus_metrics["alphabrain_benchmark_cost_usd"] = Gauge(
                    "alphabrain_benchmark_cost_usd",
                    "Total dollar cost in USD for problem",
                    ["contestant", "problem_id"],
                )
                self._prometheus_metrics["alphabrain_benchmark_tests_passed"] = Gauge(
                    "alphabrain_benchmark_tests_passed",
                    "Number of tests passed for problem",
                    ["contestant", "problem_id"],
                )
                self._prometheus_metrics["alphabrain_benchmark_speedup_ratio"] = Gauge(
                    "alphabrain_benchmark_speedup_ratio",
                    "Aggregate speedup ratio of primary contestant over opponent",
                    ["dimension"],
                )
                self._prometheus_metrics["alphabrain_benchmark_wins_total"] = Counter(
                    "alphabrain_benchmark_wins_total",
                    "Total tournament problem wins per contestant",
                    ["contestant"],
                )

            if self._summary:
                for p in self._summary.problems:
                    for c, r in p.results.items():
                        self._prometheus_metrics["alphabrain_benchmark_wall_clock_seconds"].labels(
                            contestant=c, problem_id=p.problem_id
                        ).set(r.wall_clock_seconds)
                        self._prometheus_metrics["alphabrain_benchmark_tokens_total"].labels(
                            contestant=c, problem_id=p.problem_id
                        ).set(r.total_tokens)
                        self._prometheus_metrics["alphabrain_benchmark_cost_usd"].labels(
                            contestant=c, problem_id=p.problem_id
                        ).set(r.cost_usd)
                        self._prometheus_metrics["alphabrain_benchmark_tests_passed"].labels(
                            contestant=c, problem_id=p.problem_id
                        ).set(r.tests_passed)
                if self._summary.aggregate_speedup:
                    for dim, val in self._summary.aggregate_speedup.to_dict().items():
                        numeric_val = val if val != float("inf") else 1e9
                        self._prometheus_metrics["alphabrain_benchmark_speedup_ratio"].labels(
                            dimension=dim
                        ).set(numeric_val)

            return self._prometheus_metrics
        except Exception as exc:
            logger.warning("Failed to register Prometheus metrics: %s", exc)
            return {}

    def create_fastapi_router(self) -> Any:
        """Create and return a FastAPI APIRouter mounted at /api/v1/benchmarks.

        Endpoints:
        - GET /api/v1/benchmarks/live → Full TournamentSummary JSON
        - GET /api/v1/benchmarks/live/speedup → Aggregate SpeedupRatio only
        - GET /api/v1/benchmarks/live/metrics → Prometheus text exposition

        Returns:
            fastapi.APIRouter (or None if fastapi not installed).
        Note: Uses try/except ImportError for fastapi — if not installed,
        logs warning and returns None (graceful degradation).
        """
        try:
            from fastapi import APIRouter, Response
        except ImportError:
            logger.warning("fastapi is not installed; returning None.")
            return None

        router = APIRouter(prefix="/api/v1/benchmarks")

        @router.get("/live")
        def get_live_summary() -> dict[str, Any]:
            if self._summary is None and Path(self.results_path).is_file():
                self.load_and_compute()
            return self._summary.to_dict() if self._summary else {}

        @router.get("/live/speedup")
        def get_live_speedup() -> dict[str, float]:
            if self._summary is None and Path(self.results_path).is_file():
                self.load_and_compute()
            if self._summary and self._summary.aggregate_speedup:
                return self._summary.aggregate_speedup.to_dict()
            return {}

        @router.get("/live/metrics", response_class=Response)
        def get_live_metrics():
            text = self.get_prometheus_text()
            return Response(content=text, media_type="text/plain")

        return router
