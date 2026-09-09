import subprocess
from pathlib import Path

from alpha_worker.code_review_graph import extract_code_review_graph


def test_extract_code_review_graph(tmp_path: Path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)

    # Create module A
    mod_a = repo_dir / "mod_a.py"
    mod_a.write_text("class MyClass:\n    def foo(self): pass\n")

    # Create module B depending on A
    mod_b = repo_dir / "mod_b.py"
    mod_b.write_text("from mod_a import MyClass\n")

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True)

    # Modify module A
    mod_a.write_text("class MyClass:\n    def foo(self): pass\n    def bar(self): pass\n")

    diff_content = "+++ b/mod_a.py\n--- a/mod_a.py"

    graph_md = extract_code_review_graph(str(repo_dir), diff_content)

    assert "### `mod_a.py`" in graph_md
    assert "- Class: `MyClass`" in graph_md
    assert "- Function: `foo`" in graph_md
    assert "- Function: `bar`" in graph_md
    assert "`mod_b.py`" in graph_md
