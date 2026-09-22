Write a production-grade, highly optimized Python implementation of Regular Expression Matching (LeetCode 10).

Save your implementation into a single standalone file named `regex_matching.py`.

### Target Function Signature
```python
def is_match(s: str, p: str) -> bool:
    """
    Given an input string s and a pattern p, implement regular expression matching with support for '.' and '*' where:
    - '.' Matches any single character.
    - '*' Matches zero or more of the preceding element.
    The matching should cover the entire input string (not partial).
    """
```

### Specifications & Complexity
- Must run in $O(M \cdot N)$ using 2D Dynamic Programming or memoized recursion.
- Catastrophic backtracking with overlapping '*' patterns (e.g. `a*a*a*a*a*b`) must terminate in under 5ms.

Output ONLY the complete Python code in `regex_matching.py` without markdown backticks or commentary so it can be written directly to file.
