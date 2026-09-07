from alpha_core.healing.failure_analyzer import (
    FailureAnalyzer,
    normalize_traceback,
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


def test_empty_input():
    analyzer = FailureAnalyzer()
    report = analyzer.analyze("", "")
    assert report['pytest_failures'] == []
    assert report['ruff_violations'] == []
    assert isinstance(report['signature'], str)


def test_multi_failure():
    output = """
=================================== FAILURES ===================================
_________________________ test_a __________________________
    def test_a():
>       assert 1 == 2
E       assert 1 == 2
test_file.py:10: AssertionError
_________________________ test_b __________________________
    def test_b():
>       assert 2 == 3
E       assert 2 == 3
test_file.py:15: AssertionError
=========================== short test summary info ============================
FAILED test_file.py::test_a - assert 1 == 2
FAILED test_file.py::test_b - assert 2 == 3
"""
    failures = parse_pytest_output(output)
    assert len(failures) == 2
    assert failures[0]['test_name'] == 'test_a'
    assert failures[1]['test_name'] == 'test_b'


def test_signature_determinism_proof():
    analyzer = FailureAnalyzer()
    # Different order of failures should yield same signature
    pytest_failures1 = [{'test_name': 'test_a', 'message': 'err', 'traceback': 'foo.py:10: error'}, {'test_name': 'test_b', 'message': 'err2', 'traceback': 'bar.py:20: error'}]
    pytest_failures2 = [{'test_name': 'test_b', 'message': 'err2', 'traceback': 'bar.py:20: error'}, {'test_name': 'test_a', 'message': 'err', 'traceback': 'foo.py:10: error'}]

    # Line numbers should be normalized
    pytest_failures3 = [{'test_name': 'test_a', 'message': 'err', 'traceback': 'foo.py:11: error'}, {'test_name': 'test_b', 'message': 'err2', 'traceback': 'bar.py:21: error'}]

    sig1 = analyzer.compute_signature(pytest_failures1, [])
    sig2 = analyzer.compute_signature(pytest_failures2, [])
    sig3 = analyzer.compute_signature(pytest_failures3, [])

    assert sig1 == sig2
    assert sig1 == sig3


def test_parameterized_test_names():
    output = """
=================================== FAILURES ===================================
_________________________ test_func[param1] __________________________
    def test_func():
>       assert False
E       assert False
test_file.py:10: AssertionError
=========================== short test summary info ============================
FAILED test_file.py::test_func[param1] - assert False
FAILED test_file.py::test_func[param2] - assert False
"""
    failures = parse_pytest_output(output)
    assert len(failures) == 2
    assert failures[0]['test_name'] == 'test_func[param1]'
    assert failures[0]['traceback'] != ''
    assert failures[1]['test_name'] == 'test_func[param2]'


def test_failures_block_without_summary():
    output = """
=================================== FAILURES ===================================
_________________________ test_without_summary __________________________
    def test_without_summary():
>       assert False
E       assert False
test_file.py:10: AssertionError
"""
    failures = parse_pytest_output(output)
    assert len(failures) == 1
    assert failures[0]['test_name'] == 'test_without_summary'
    assert 'assert False' in failures[0]['traceback']


def test_normalize_traceback_isolation():
    tb_input = "test_file.py:123: AssertionError\n  123 | assert False"
    tb_output = normalize_traceback(tb_input)
    assert "test_file.py:123:" not in tb_output
    assert "FILE:LINE:" in tb_output
    assert "LINE |" in tb_output


def test_malformed_ruff_input():
    output = "This is some junk output\\nthat shouldn't match anything."
    violations = parse_ruff_output(output)
    assert violations == []
