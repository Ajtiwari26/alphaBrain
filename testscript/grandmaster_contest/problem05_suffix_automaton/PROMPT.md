Write a production-grade, highly optimized Python implementation of Shortest Unique Common Substring (Codeforces 427D - Match & Catch / Suffix Automaton).

Save your implementation into a single standalone file named `match_catch.py`.

### Target Function Signature
```python
def shortest_unique_common_substring(s1: str, s2: str) -> int:
    """
    You are given two strings s1 and s2.
    Find the length of the shortest substring that appears EXACTLY ONCE in s1 AND EXACTLY ONCE in s2.
    If no such substring exists, return -1.
    Overall time complexity must be O((|s1| + |s2|) * log Sigma) using a Suffix Automaton (SAM)
    or Suffix Array + LCP with monotonic deque.
    """
```

### Specifications & Complexity
- Standard substring hashing or pairwise comparison runs in $O(N^2)$ or $O(N^3)$ and will strictly TLE on $|s_1|, |s_2| = 10,000$.
- Must use a **Suffix Automaton (SAM)** or **Suffix Array** tracking state occurrence counts (endpos size) across both strings.
- Combined string $S = s_1 + \# + s_2 + \$$ with distinct delimiters.
- In the Suffix Automaton link tree, state $u$ is valid if and only if $cnt_1[u] == 1$ and $cnt_2[u] == 1$.
- The length of the shortest substring represented by state $u$ is $len(link[u]) + 1$.
- Handle completely disjoint alphabets, identical strings, strings with only 1 unique match, and strings where no unique common substring exists.

Output ONLY the complete Python code in `match_catch.py` without markdown backticks or commentary so it can be written directly to file.
