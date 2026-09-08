from alpha_core.healing.repair_synthesizer import RepairEnvelopeSynthesizer


def test_synthesizer_bounds_allowed_paths():
    synth = RepairEnvelopeSynthesizer("tsk_123", 1)
    # I-37 ensures repo-wide paths like '.' and '/' are removed
    bounded = synth.bound_allowed_paths(["alpha_core/healing/", "."], ["test_file.py"])
    assert "." not in bounded
    assert "alpha_core/healing/" in bounded
    assert "test_file.py" in bounded


def test_synthesizer_links_parent_and_epoch():
    synth = RepairEnvelopeSynthesizer("tsk_123", 1)
    assert synth.parent_task_id == "tsk_123"
    assert synth.repair_epoch == 1


def test_synthesizer_formats_actionable_prompt():
    synth = RepairEnvelopeSynthesizer("tsk_123", 1)
    failures = {
        "pytest_failures": [{"file": "test_file.py"}],
        "ruff_violations": [{"file": "other.py"}],
        "signature": "abc123hash",
    }
    result = synth.synthesize(["alpha_core/", "test_file.py", "other.py"], failures, "prj_1", "/worktree")

    assert result["parent_task_id"] == "tsk_123"
    assert result["repair_epoch"] == 1
    assert "test_file.py" in result["allowed_paths"]
    assert "other.py" in result["allowed_paths"]
    assert "alpha_core/" in result["allowed_paths"]

    prompt = result["actionable_prompt"]
    assert "tsk_123" in prompt
    assert "Epoch 1" in prompt
    assert "abc123hash" in prompt
    assert "Actionable repair prompt" in prompt
