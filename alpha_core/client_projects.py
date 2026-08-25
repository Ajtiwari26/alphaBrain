"""Client-project registry: Alpha Brain pointers, never client source storage."""

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from alpha_core.config import settings


@dataclass(frozen=True)
class ClientProjectLink:
    project_id: str
    repo_path: str
    requirements_path: str
    antigravity_project_id: str | None
    antigravity_conversation_id: str | None
    created_at: str


class ClientProjectRegistry:
    """Stores safe pointers from Alpha Brain to separately versioned client repos."""

    _ID = re.compile(r"^[a-z][a-z0-9_-]{2,62}$")

    def __init__(self, root: Path | None = None, memory_graph: Path | None = None) -> None:
        self.root = (root or settings.CLIENT_PROJECTS_ROOT).expanduser().resolve()
        self.store = (memory_graph or settings.MEMORY_GRAPH_PATH) / "alphaBrain-projects"

    def register_existing(
        self,
        project_id: str,
        repo_path: Path,
        requirements_path: Path,
        antigravity_project_id: str | None = None,
        antigravity_conversation_id: str | None = None,
    ) -> ClientProjectLink:
        if not self._ID.fullmatch(project_id):
            raise ValueError("Invalid client project ID")
        repo = repo_path.expanduser().resolve()
        requirements = requirements_path.expanduser().resolve()
        if not repo.is_relative_to(self.root) or not (repo / ".git").exists():
            raise ValueError("Client repository must be a Git repo under CLIENT_PROJECTS_ROOT")
        if not requirements.is_relative_to(repo) or not requirements.is_file():
            raise ValueError("Requirements document must exist inside client repository")
        link = ClientProjectLink(
            project_id=project_id,
            repo_path=str(repo),
            requirements_path=str(requirements.relative_to(repo)),
            antigravity_project_id=antigravity_project_id,
            antigravity_conversation_id=antigravity_conversation_id,
            created_at=datetime.now(UTC).isoformat(),
        )
        self.store.mkdir(parents=True, exist_ok=True)
        (self.store / f"{project_id}.json").write_text(json.dumps(asdict(link), indent=2) + "\n")
        return link
