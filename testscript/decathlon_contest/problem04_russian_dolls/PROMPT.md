Write a production-grade, highly optimized Python implementation of Russian Doll Envelopes (LeetCode 354).

Save your implementation into a single standalone file named `russian_dolls.py`.

### Target Function Signature
```python
def max_envelopes(envelopes: list[list[int]]) -> int:
    """
    You are given a 2D array of integers envelopes where envelopes[i] = [w_i, h_i] represents the width and height of an envelope.
    One envelope can fit into another if and only if both the width and height of one envelope are strictly greater than the other envelope.
    Return the maximum number of envelopes you can Russian doll (i.e., put one inside the other).
    Note: You cannot rotate an envelope.
    """
```

### Specifications & Complexity
- Constraints: 1 <= envelopes.length <= 10^5.
- Must run in $O(N \log N)$ time (e.g. sorting by width asc, height desc, then patience sort/binary search LIS).
- Naive $O(N^2)$ DP will strictly TLE on large inputs.

Output ONLY the complete Python code in `russian_dolls.py` without markdown backticks or commentary so it can be written directly to file.
