import hashlib
import re
from typing import Any


def parse_pytest_output(output: str) -> list[dict[str, str]]:
    summary_pattern = re.compile(r"^FAILED\s+(.*?)::([^\s]+)\s+(?:-|)\s*(.*)$", re.MULTILINE)
    summaries = {}
    for match in summary_pattern.finditer(output):
        file_path, test_name, message = match.groups()
        summaries[test_name] = {
            "file": file_path,
            "test_name": test_name.strip(),
            "message": message.strip(),
            "traceback": ""
        }

    failures_start = output.find("FAILURES ")
    if failures_start != -1:
        summary_start = output.find(" short test summary info ")
        if summary_start == -1:
            summary_start = len(output)
        else:
            summary_start = output.rfind("\n", 0, summary_start)
            if summary_start == -1:
                summary_start = len(output)

        failures_block = output[failures_start:summary_start]
        blocks = re.split(r"_{10,}\s+([a-zA-Z0-9_]+)\s+_{10,}", failures_block)
        for i in range(1, len(blocks), 2):
            test_name = blocks[i].strip()
            traceback = blocks[i+1].strip()
            traceback = re.sub(r"\n=+$", "", traceback).strip()
            if test_name in summaries:
                summaries[test_name]["traceback"] = traceback
            else:
                summaries[test_name] = {
                    "file": "",
                    "test_name": test_name,
                    "message": "",
                    "traceback": traceback
                }

    return list(summaries.values())

def parse_ruff_output(output: str) -> list[dict[str, str]]:
    violations = []
    # Match lines like "file.py:line:col: CODE message"
    pattern = re.compile(r"^\s*([^:]+):\d+:\d+:\s+([A-Z0-9]+)\s+(.*)$", re.MULTILINE)
    for match in pattern.finditer(output):
        violations.append({
            "file": match.group(1).strip(),
            "code": match.group(2),
            "message": match.group(3).strip()
        })
    return violations

class FailureAnalyzer:
    def compute_signature(self, pytest_failures: list[dict[str, str]], ruff_violations: list[dict[str, str]]) -> str:
        # Create a stable string representation
        components = []
        for f in sorted(pytest_failures, key=lambda x: x.get('test_name', '')):
            components.append(f"pytest:{f.get('test_name')}:{f.get('message')}:{f.get('traceback', '')}")
        for v in sorted(ruff_violations, key=lambda x: (x.get('file', ''), x.get('code', ''))):
            components.append(f"ruff:{v.get('file')}:{v.get('code')}")

        signature_input = "|".join(components)
        return hashlib.sha256(signature_input.encode('utf-8')).hexdigest()

    def analyze(self, pytest_output: str, ruff_output: str) -> dict[str, Any]:
        pytest_failures = parse_pytest_output(pytest_output)
        ruff_violations = parse_ruff_output(ruff_output)

        return {
            "pytest_failures": pytest_failures,
            "ruff_violations": ruff_violations,
            "signature": self.compute_signature(pytest_failures, ruff_violations)
        }
