from alpha_core.healing.failure_analyzer import (
    FailureAnalyzer,
    parse_pytest_output,
    parse_ruff_output,
)


def test_parse_pytest_output():
    output = """
=================================== FAILURES ===================================
_________________________ test_something_that_fails __________________________

    def test_something_that_fails():
>       assert 1 == 2
E       assert 1 == 2

test_file.py:10: AssertionError
=========================== short test summary info ============================
FAILED test_file.py::test_something_that_fails - assert 1 == 2
"""
    failures = parse_pytest_output(output)
    assert len(failures) == 1
    assert failures[0]['test_name'] == 'test_something_that_fails'
    assert 'assert 1 == 2' in failures[0]['message']
    assert 'AssertionError' in failures[0]['traceback']

def test_parse_ruff_output():
    output = """
alpha_core/healing/failure_analyzer.py:10:5: F401 `os` imported but unused
alpha_core/healing/failure_analyzer.py:12:1: E302 expected 2 blank lines, found 1
Found 2 errors.
"""
    violations = parse_ruff_output(output)
    assert len(violations) == 2
    assert violations[0]['file'] == 'alpha_core/healing/failure_analyzer.py'
    assert violations[0]['code'] == 'F401'
    assert violations[0]['message'] == '`os` imported but unused'
    assert violations[1]['code'] == 'E302'

def test_compute_failure_signature():
    pytest_failures = [{'test_name': 'test_a', 'message': 'assert 1 == 2'}]
    ruff_violations = [{'file': 'file.py', 'code': 'F401', 'message': 'unused'}]

    analyzer = FailureAnalyzer()
    sig = analyzer.compute_signature(pytest_failures, ruff_violations)

    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA256 length

def test_failure_analyzer_integration():
    analyzer = FailureAnalyzer()
    pytest_out = "FAILED test_x.py::test_x - AssertionError"
    ruff_out = "file.py:1:1: E501 line too long"

    report = analyzer.analyze(pytest_out, ruff_out)
    assert 'pytest_failures' in report
    assert 'ruff_violations' in report
    assert 'signature' in report
    assert report['pytest_failures'][0]['test_name'] == 'test_x'
    assert report['ruff_violations'][0]['code'] == 'E501'
