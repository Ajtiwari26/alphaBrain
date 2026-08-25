from pathlib import Path

import pytest

from alpha_core.client_projects import ClientProjectRegistry


def test_registry_stores_pointer_not_client_source(tmp_path: Path):
    root = tmp_path / "clientProjects"
    repo = root / "calculator"
    requirements = repo / "docs" / "requirements" / "approved-spec.md"
    requirements.parent.mkdir(parents=True)
    (repo / ".git").mkdir()
    requirements.write_text("# Approved calculator spec\n")
    registry = ClientProjectRegistry(root, tmp_path / "memory")

    link = registry.register_existing("prj_calculator", repo, requirements)

    assert link.repo_path == str(repo)
    assert link.requirements_path == "docs/requirements/approved-spec.md"
    assert (tmp_path / "memory" / "alphaBrain-projects" / "prj_calculator.json").is_file()


def test_registry_rejects_client_source_outside_root(tmp_path: Path):
    repo = tmp_path / "outside"
    repo.mkdir()
    (repo / ".git").mkdir()
    requirements = repo / "approved-spec.md"
    requirements.write_text("spec")
    with pytest.raises(ValueError, match="CLIENT_PROJECTS_ROOT"):
        ClientProjectRegistry(tmp_path / "clientProjects", tmp_path / "memory").register_existing(
            "prj_outside", repo, requirements
        )
