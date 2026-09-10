from alpha_core.utils.text_helpers import normalize_task_slug


def test_normalize_task_slug():
    # C1: convert to lowercase
    assert normalize_task_slug("HELLO WORLD") == "hello-world"

    # C2: replace whitespace and symbols with hyphens
    assert normalize_task_slug("hello@world#test") == "hello-world-test"

    # C3: collapse consecutive hyphens into single hyphen
    assert normalize_task_slug("hello   world") == "hello-world"
    assert normalize_task_slug("hello---world") == "hello-world"

    # C4: strip leading and trailing hyphens
    assert normalize_task_slug("---hello-world---") == "hello-world"
    assert normalize_task_slug("   hello world   ") == "hello-world"

    # C5: truncate to max_length without trailing hyphen
    long_string = "a" * 60
    slug = normalize_task_slug(long_string)
    assert len(slug) == 50
    assert slug == "a" * 50

    # Truncation results in trailing hyphen which should be stripped
    str_with_hyphen = "a" * 49 + " bbb"
    assert normalize_task_slug(str_with_hyphen) == "a" * 49

    # Custom max_length
    assert normalize_task_slug("hello world", max_length=5) == "hello"

    # C6: return fallback 'task' for empty or non-alphanumeric input
    assert normalize_task_slug("") == "task"
    assert normalize_task_slug("    ") == "task"
    assert normalize_task_slug("!@#$%") == "task"
    assert normalize_task_slug("---") == "task"

    # C7: pure function without external dependencies (tested implicitly by execution)

    import pytest
    with pytest.raises(ValueError, match="at least 1"):
        normalize_task_slug("test", max_length=0)

    # Hardening tests
    assert normalize_task_slug("µñîçø∂é") == "task"  # unicode non-ascii strips to empty
    assert normalize_task_slug("12345") == "12345"
    assert normalize_task_slug("a") == "a"
    assert normalize_task_slug("", max_length=2) == "ta"
