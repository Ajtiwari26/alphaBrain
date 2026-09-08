from typing import Any


class RepairEnvelopeSynthesizer:
    def __init__(self, parent_task_id: str, repair_epoch: int):
        self.parent_task_id = parent_task_id
        self.repair_epoch = repair_epoch

    def bound_allowed_paths(self, original_paths: list[str], failed_files: list[str]) -> list[str]:
        paths = set(original_paths)
        for f in failed_files:
            if f:
                paths.add(f)
        paths.discard(".")
        paths.discard("/")
        paths.discard("")
        return sorted(paths)

    def synthesize(
        self, original_paths: list[str], failures: dict[str, Any], project_id: str, worktree: str
    ) -> dict[str, Any]:
        failed_files = []
        for pf in failures.get("pytest_failures", []):
            if pf.get("file"):
                failed_files.append(pf["file"])
        for rv in failures.get("ruff_violations", []):
            if rv.get("file"):
                failed_files.append(rv["file"])

        bounded_paths = self.bound_allowed_paths(original_paths, failed_files)

        prompt = (
            f"Repair Task for {self.parent_task_id} (Epoch {self.repair_epoch})\n"
            f"Project: {project_id}\n"
            f"Worktree: {worktree}\n"
            f"Bounded Paths (I-37): {', '.join(bounded_paths)}\n"
            f"Signature: {failures.get('signature', 'N/A')}\n\n"
            "Actionable repair prompt: Please address the test and lint failures."
        )

        return {
            "parent_task_id": self.parent_task_id,
            "repair_epoch": self.repair_epoch,
            "allowed_paths": bounded_paths,
            "actionable_prompt": prompt,
        }
