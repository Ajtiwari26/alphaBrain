"""
alpha_core/automation/todo_sync.py
Autonomous TODO and Roadmap State Machine Synchronization Engine.

Atomically updates TODO.md and docs/architecture/NEXT_PHASE_ROADMAP.md upon
task merge into main, recording completion status, commit SHA, and task ID.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _atomic_write_file(filepath: Path, content: str) -> None:
    """Atomically write text content to filepath using tempfile and os.replace."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=filepath.parent, prefix=f".tmp_{filepath.name}_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, filepath)
        try:
            dir_fd = os.open(filepath.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            os.fsync(dir_fd)
            os.close(dir_fd)
        except OSError:
            pass
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _extract_keywords(text: str) -> set[str]:
    """Extract significant lowercase keywords for fuzzy matching."""
    stop_words = {
        "a", "an", "the", "and", "or", "to", "in", "on", "for", "with",
        "of", "at", "by", "from", "as", "is", "are", "implement", "engine",
        "task", "autonomous", "state", "machine",
    }
    words = re.findall(r"[a-zA-Z0-9_-]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in stop_words}


@dataclass
class _TaskBlock:
    start: int
    end: int
    first_line: str
    raw_block: str
    is_in_active: bool


def _extract_task_blocks(content: str) -> list[_TaskBlock]:
    """
    Extract all task blocks starting with '### ' from markdown content,
    recording their exact start/end character bounds, heading, raw text,
    and whether they reside in an active section.
    """
    delim_pattern = re.compile(r"^(?:#{1,3}\s+.*|---\s*)$", re.MULTILINE)
    delims = list(delim_pattern.finditer(content))
    blocks: list[_TaskBlock] = []

    for idx, m in enumerate(delims):
        line = m.group(0)
        if line.startswith("### "):
            start = m.start()
            end = delims[idx + 1].start() if (idx + 1 < len(delims)) else len(content)
            raw_block = content[start:end].rstrip()
            first_line = raw_block.splitlines()[0] if raw_block else line

            preceding = content[:start]
            active_pos = preceding.rfind("## Active")
            completed_pos = preceding.rfind("## Completed")
            is_in_active = (active_pos > completed_pos and active_pos != -1)

            blocks.append(
                _TaskBlock(
                    start=start,
                    end=end,
                    first_line=first_line,
                    raw_block=raw_block,
                    is_in_active=is_in_active,
                )
            )

    return blocks


def _surgically_update_task_block(
    raw_block: str,
    status_line: str,
    objective: str | None = None,
) -> str:
    """
    Surgically update a task block's status line (and objective if provided/missing),
    preserving all existing metadata fields, custom developer notes, and structure.
    """
    lines = raw_block.splitlines(keepends=True)
    if not lines:
        return status_line

    if not lines[0].endswith("\n"):
        lines[0] += "\n"

    status_idx = -1
    for idx, line in enumerate(lines[1:], start=1):
        if re.match(r"^\s*-\s*\*\*Status\*\*:", line):
            status_idx = idx
            break

    if status_idx != -1:
        lines[status_idx] = status_line
    else:
        lines.insert(1, status_line)

    obj_idx = -1
    for idx, line in enumerate(lines[1:], start=1):
        if re.match(r"^\s*-\s*\*\*Objective\*\*:", line):
            obj_idx = idx
            break

    if obj_idx != -1:
        if objective and objective.strip():
            lines[obj_idx] = f"- **Objective**: {objective.strip()}\n"
    else:
        if objective and objective.strip():
            curr_status_idx = -1
            for idx, line in enumerate(lines[1:], start=1):
                if re.match(r"^\s*-\s*\*\*Status\*\*:", line):
                    curr_status_idx = idx
                    break
            insert_at = (curr_status_idx + 1) if curr_status_idx != -1 else 2
            lines.insert(insert_at, f"- **Objective**: {objective.strip()}\n")

    return "".join(lines)


def _insert_into_completed_section(content: str, block_to_insert: str) -> str:
    """
    Insert a task block into the Completed section before any trailing horizontal
    divider or next major section (such as ## Active).
    """
    completed_match = re.search(r"^##\s+Completed", content, flags=re.MULTILINE | re.IGNORECASE)
    if completed_match:
        comp_start = completed_match.start()
        sub_text = content[comp_start:]
        header_line_end = sub_text.find("\n")
        if header_line_end != -1:
            search_offset = comp_start + header_line_end + 1
            search_slice = content[search_offset:]
            boundary_match = re.search(
                r"^(?:---\s*$|##\s+(?!Completed))",
                search_slice,
                flags=re.MULTILINE | re.IGNORECASE,
            )
            if boundary_match:
                insert_pos = search_offset + boundary_match.start()
            else:
                insert_pos = len(content)
        else:
            insert_pos = len(content)
    else:
        boundary_match = re.search(
            r"^(?:---\s*$|##\s+Active)", content, flags=re.MULTILINE | re.IGNORECASE
        )
        if boundary_match:
            insert_pos = boundary_match.start()
        else:
            insert_pos = len(content)

    before = content[:insert_pos].rstrip()
    after = content[insert_pos:].lstrip("\n")
    if after:
        return f"{before}\n\n{block_to_insert.rstrip()}\n\n{after}"
    else:
        return f"{before}\n\n{block_to_insert.rstrip()}\n"


class TodoSyncEngine:
    """
    Durable engine that synchronizes task completion across TODO.md and
    docs/architecture/NEXT_PHASE_ROADMAP.md upon task promotion / merge.
    """

    def __init__(
        self,
        repo_path: Path | str = ".",
        todo_path: Path | str | None = None,
        roadmap_path: Path | str | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.todo_path = Path(todo_path).resolve() if todo_path else (self.repo_path / "TODO.md")
        self.roadmap_path = (
            Path(roadmap_path).resolve()
            if roadmap_path
            else (self.repo_path / "docs" / "architecture" / "NEXT_PHASE_ROADMAP.md")
        )

    def _format_short_sha(self, commit_sha: str) -> str:
        """Format commit SHA to 7-character short SHA."""
        sha = commit_sha.strip()
        return sha[:7] if len(sha) >= 7 else sha

    def update_todo(
        self,
        task_id: str,
        commit_sha: str,
        title: str | None = None,
    ) -> bool:
        """
        Atomically mark task complete in TODO.md with commit SHA and task ID.
        Returns True if the file was modified, False if already up to date.
        """
        short_sha = self._format_short_sha(commit_sha)
        item_title = title.strip() if title else ""
        keywords = _extract_keywords(item_title) if item_title else set()

        content = ""
        if self.todo_path.exists():
            content = self.todo_path.read_text(encoding="utf-8")

        if not content:
            initial_content = (
                "# Alpha Brain Development TODO\n\n"
                "## Current implementation baseline\n\n"
                "### Implemented foundation\n\n"
                f"- [x] {item_title or task_id} (`commit {short_sha}`, `{task_id}`).\n"
            )
            _atomic_write_file(self.todo_path, initial_content)
            return True

        # Idempotency check: already marked complete with this task_id and short_sha
        lines = content.splitlines(keepends=True)
        for line in lines:
            if re.search(r"^\s*-\s*\[[xX]\]", line) and task_id in line and short_sha in line:
                return False

        matched_idx = -1

        # Match strategy 1: Look for exact task_id in any checklist line
        for i, line in enumerate(lines):
            if re.search(r"^\s*-\s*\[[ x\-]\]", line) and task_id in line:
                matched_idx = i
                break

        # Match strategy 2: Check for title / keyword match in incomplete checklist items
        if matched_idx == -1 and item_title:
            best_score = 0
            best_idx = -1
            clean_title = re.sub(r"[^a-zA-Z0-9\s]", "", item_title).strip().lower()

            for i, line in enumerate(lines):
                if not re.search(r"^\s*-\s*\[\s*\]", line):
                    continue
                clean_line = re.sub(r"[^a-zA-Z0-9\s]", "", line).strip().lower()
                if clean_title in clean_line:
                    best_idx = i
                    break
                if keywords:
                    line_words = _extract_keywords(line)
                    overlap = len(keywords.intersection(line_words))
                    if overlap > best_score and overlap >= 2:
                        best_score = overlap
                        best_idx = i

            if best_idx != -1:
                matched_idx = best_idx

        # If matched, update the line in place
        if matched_idx != -1:
            orig_line = lines[matched_idx]
            # Replace - [ ] or - [-] with - [x]
            new_line = re.sub(r"^(\s*-\s*)\[[ \-]\]", r"\1[x]", orig_line)

            # Strip existing trailing commit/task refs or standalone task ID refs if updating
            new_line = re.sub(r"\s*\(`commit [a-f0-9]+`,\s*`[^`]+`\)\.?", "", new_line)
            new_line = re.sub(rf"\s*\(`{re.escape(task_id)}`\)\.?", "", new_line)
            new_line = re.sub(r"\s*\(`tsk_[a-zA-Z0-9_-]+`\)\.?", "", new_line)
            new_line = new_line.rstrip("\r\n")
            if new_line.endswith("."):
                new_line = new_line[:-1]

            new_line = f"{new_line} (`commit {short_sha}`, `{task_id}`).\n"
            lines[matched_idx] = new_line
            _atomic_write_file(self.todo_path, "".join(lines))
            return True

        # Match strategy 3: Item not found, append under Implemented foundation
        target_section = "### Implemented foundation"
        inserted = False
        new_lines: list[str] = []
        in_target = False

        for line in lines:
            new_lines.append(line)
            if target_section.lower() in line.lower():
                in_target = True
                continue
            if in_target and (line.startswith("### ") or line.startswith("## ")):
                # Insert right before next heading
                new_lines.insert(
                    len(new_lines) - 1,
                    f"- [x] {item_title or task_id} (`commit {short_sha}`, `{task_id}`).\n\n",
                )
                inserted = True
                in_target = False

        if in_target and not inserted:
            new_lines.append(
                f"- [x] {item_title or task_id} (`commit {short_sha}`, `{task_id}`).\n"
            )
            inserted = True

        if not inserted:
            new_lines.append(
                f"\n- [x] {item_title or task_id} (`commit {short_sha}`, `{task_id}`).\n"
            )

        _atomic_write_file(self.todo_path, "".join(new_lines))
        return True

    def update_roadmap(
        self,
        task_id: str,
        commit_sha: str,
        title: str | None = None,
        objective: str | None = None,
        status: str = "COMPLETED & MERGED",
    ) -> bool:
        """
        Atomically promote task in NEXT_PHASE_ROADMAP.md with completion status,
        commit SHA, and task ID. Surgically preserves all other fields and headers.
        Returns True if the file was modified, False if already up to date.
        """
        short_sha = self._format_short_sha(commit_sha)
        item_title = title.strip() if title else ""
        item_obj = objective.strip() if objective else ""
        keywords = _extract_keywords(item_title) if item_title else set()

        content = ""
        if self.roadmap_path.exists():
            content = self.roadmap_path.read_text(encoding="utf-8")

        if not content:
            initial_content = (
                "# AlphaBrain Next Phase Roadmap\n\n"
                "## Completed & Merged Milestones\n\n"
                f"### {item_title or task_id}\n"
                f"- **Status**: `[x] {status}` (`commit {short_sha}`, `{task_id}`)\n"
                f"- **Objective**: {item_obj or item_title or task_id}\n"
            )
            _atomic_write_file(self.roadmap_path, initial_content)
            return True

        # Idempotency check: already in roadmap with task_id and short_sha and status
        idempotent_pattern = re.compile(
            rf"\*\*Status\*\*:\s*`\[x\]\s*{re.escape(status)}`\s*\(`commit {re.escape(short_sha)}`,\s*`{re.escape(task_id)}`\)",
            re.MULTILINE,
        )
        if idempotent_pattern.search(content):
            return False

        # Parse roadmap task blocks
        task_blocks = _extract_task_blocks(content)
        matched_block: _TaskBlock | None = None

        if task_id:
            for blk in task_blocks:
                if task_id in blk.raw_block:
                    matched_block = blk
                    break

        if matched_block is None and item_title:
            clean_title = re.sub(r"[^a-zA-Z0-9\s]", "", item_title).strip().lower()
            for blk in task_blocks:
                clean_heading = re.sub(r"[^a-zA-Z0-9\s]", "", blk.first_line).strip().lower()
                if clean_title and (clean_title in clean_heading or clean_heading in clean_title):
                    matched_block = blk
                    break
                # Check Task Title in block
                matched_tt = False
                for line in blk.raw_block.splitlines():
                    if "**Task Title**:" in line:
                        tt_val = line.split("**Task Title**:", 1)[1].strip().lower()
                        clean_tt = re.sub(r"[^a-zA-Z0-9\s]", "", tt_val).strip()
                        if clean_title and (clean_title in clean_tt or clean_tt in clean_title):
                            matched_tt = True
                            break
                if matched_tt:
                    matched_block = blk
                    break
                if keywords:
                    sec_words = _extract_keywords(blk.first_line)
                    if len(keywords.intersection(sec_words)) >= 2:
                        matched_block = blk
                        break

        status_line = (
            f"- **Status**: `[x] {status}` (`commit {short_sha}`, `{task_id}`)\n"
        )

        if matched_block is not None:
            new_block = _surgically_update_task_block(
                raw_block=matched_block.raw_block,
                status_line=status_line,
                objective=item_obj or None,
            )

            if matched_block.is_in_active:
                before_task = content[:matched_block.start].rstrip("\n")
                after_task = content[matched_block.end:].lstrip("\n")
                content_without_task = f"{before_task}\n\n{after_task}"
                updated_content = _insert_into_completed_section(content_without_task, new_block)
            else:
                before = content[:matched_block.start].rstrip()
                after = content[matched_block.end:].lstrip("\n")
                if after:
                    updated_content = f"{before}\n\n{new_block.rstrip()}\n\n{after}"
                else:
                    updated_content = f"{before}\n\n{new_block.rstrip()}\n"

            _atomic_write_file(self.roadmap_path, updated_content)
            return True

        # Task not found anywhere in document, append to Completed
        new_entry = (
            f"### {item_title or task_id}\n"
            f"{status_line}"
            f"- **Objective**: {item_obj or item_title or task_id}\n"
        )
        updated_content = _insert_into_completed_section(content, new_entry)
        _atomic_write_file(self.roadmap_path, updated_content)
        return True

    def sync(
        self,
        task_id: str,
        commit_sha: str,
        title: str | None = None,
        objective: str | None = None,
        status: str = "COMPLETED & MERGED",
    ) -> dict[str, bool]:
        """
        Synchronizes both TODO.md and NEXT_PHASE_ROADMAP.md atomically.
        """
        todo_updated = self.update_todo(
            task_id=task_id, commit_sha=commit_sha, title=title
        )
        roadmap_updated = self.update_roadmap(
            task_id=task_id,
            commit_sha=commit_sha,
            title=title,
            objective=objective,
            status=status,
        )
        return {"todo_updated": todo_updated, "roadmap_updated": roadmap_updated}


def sync_task_completion(
    repo_path: Path | str = ".",
    task_id: str = "",
    commit_sha: str = "",
    task: dict[str, Any] | None = None,
    todo_path: Path | str | None = None,
    roadmap_path: Path | str | None = None,
) -> dict[str, bool]:
    """
    Convenience wrapper to extract metadata from task dict and trigger
    TodoSyncEngine synchronization.
    """
    effective_task_id = task_id
    if not effective_task_id and task:
        effective_task_id = task.get("id", "")

    effective_sha = commit_sha
    if not effective_sha and task:
        result = task.get("result") or {}
        effective_sha = result.get("result_sha", "")

    title: str | None = None
    objective: str | None = None
    if task:
        envelope = task.get("envelope") or {}
        title = envelope.get("title") or envelope.get("objective") or envelope.get("description")
        objective = envelope.get("objective") or envelope.get("description") or envelope.get("title")

    engine = TodoSyncEngine(
        repo_path=repo_path,
        todo_path=todo_path,
        roadmap_path=roadmap_path,
    )
    return engine.sync(
        task_id=effective_task_id,
        commit_sha=effective_sha,
        title=title,
        objective=objective,
    )
