Write a production-grade, highly optimized Python implementation of Minimum Window Substring (LeetCode 76).

Save your implementation into a single standalone file named `min_window.py`.

### Target Function Signature
```python
def min_window(s: str, t: str) -> str:
    """
    Given two strings s and t of lengths m and n respectively, return the minimum window substring
    of s such that every character in t (including duplicates) is included in the window.
    If there is no such substring, return the empty string "".
    If there are multiple such minimum-length substrings, return the one that occurs first in s.
    The overall run time complexity must be O(m + n).
    """
```

### Specifications & Complexity
- Must run in strict $O(m + n)$ time using the two-pointer sliding window technique with frequency arrays or hash tables.
- Accurately handle duplicate characters in `t`, single-character strings, cases where `t` is longer than `s`, and case sensitivity ('A' != 'a').
- Must comfortably pass stress tests with $|s| = 100,000$ and $|t| = 1,000$ in $< 100$ms.

Output ONLY the complete Python code in `min_window.py` without markdown backticks or commentary so it can be written directly to file.
