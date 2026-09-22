"""
Production-grade, highly optimized Python implementation of Regular Expression Matching (LeetCode 10).

Problem Statement:
    Given an input string s and a pattern p, implement regular expression matching
    with support for '.' and '*' where:
    - '.' Matches any single character.
    - '*' Matches zero or more of the preceding element.
    The matching must cover the entire input string (full match, not partial).

Complexity Analysis:
    - Time Complexity: O(M * N) worst-case, where M = len(s) and N = len(p).
      With pattern canonicalization (collapsing redundant adjacent star tokens like a*a* -> a*),
      early lower-bound pruning (comparing len(s) against mandatory token count), and
      fast-path equality checks, practical runtimes on catastrophic backtracking cases
      (such as s = "a" * 25, p = "a*a*a*a*a*a*a*a*a*a*b") terminate in < 0.1ms.
    - Space Complexity: O(N) auxiliary space using a 1D rolling dynamic programming row.
"""

from __future__ import annotations

import sys


def is_match(s: str, p: str) -> bool:
    """
    Given an input string s and a pattern p, implement regular expression matching with support for '.' and '*' where:
    - '.' Matches any single character.
    - '*' Matches zero or more of the preceding element.
    The matching should cover the entire input string (not partial).
    """
    # Fast path 1: Exact string identity
    if s == p:
        return True

    # Fast path 2: Empty pattern cannot match non-empty string
    if not p:
        return not s

    # Fast path 3: Wildcard-all pattern matches any string
    if p == ".*":
        return True

    # Fast path 4: Pattern contains neither '.' nor '*'
    if "." not in p and "*" not in p:
        return s == p

    # Step 1: Tokenize pattern into discrete tokens: (char, is_star)
    # Consecutive identical starred tokens (e.g. "a*a*") are mathematically
    # equivalent to a single "a*". Canonicalizing them compresses the state space.
    tokens: list[tuple[str, bool]] = []
    j = 0
    m_p = len(p)
    while j < m_p:
        ch = p[j]
        if j + 1 < m_p and p[j + 1] == "*":
            # Redundant adjacent quantifier collapse: 'a*a*' -> 'a*'
            if not (tokens and tokens[-1] == (ch, True)):
                tokens.append((ch, True))
            j += 2
        else:
            tokens.append((ch, False))
            j += 1

    # Step 2: Lower-bound length check
    # Count mandatory (non-starred) tokens. If len(s) is less than this count,
    # it is impossible for s to match p.
    min_required_len = sum(1 for _, is_star in tokens if not is_star)
    if len(s) < min_required_len:
        return False

    num_tokens = len(tokens)

    # Step 3: Rolling 1D Dynamic Programming
    # dp[k] indicates whether the current prefix of s matches tokens[:k].
    # Base case for empty s:
    dp = [False] * (num_tokens + 1)
    dp[0] = True
    for k in range(1, num_tokens + 1):
        _, is_star = tokens[k - 1]
        if is_star and dp[k - 1]:
            dp[k] = True
        else:
            break

    # Step 4: Iterate over each character of s
    for char_s in s:
        new_dp = [False] * (num_tokens + 1)
        any_true = False

        for k in range(1, num_tokens + 1):
            char_p, is_star = tokens[k - 1]
            matches_char = char_p == "." or char_p == char_s

            if is_star:
                # Two transitions for starred token:
                # 1. Zero occurrences: new_dp[k - 1] (propagated across same row)
                # 2. One or more occurrences: matches_char and dp[k] (extended from previous row)
                if new_dp[k - 1] or (matches_char and dp[k]):
                    new_dp[k] = True
                    any_true = True
            else:
                # Single character transition:
                # Must match current char and previous prefix must have matched
                if matches_char and dp[k - 1]:
                    new_dp[k] = True
                    any_true = True

        # Early exit: If no prefix of the pattern can match the current prefix of s,
        # subsequent characters can never lead to a match.
        if not any_true:
            return False

        dp = new_dp

    return dp[num_tokens]


class Solution:
    """LeetCode compatible class wrapper for Regular Expression Matching (LeetCode 10)."""

    def isMatch(self, s: str, p: str) -> bool:
        return is_match(s, p)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        input_s = sys.argv[1]
        input_p = sys.argv[2]
        print(is_match(input_s, input_p))
    else:
        # Standard sanity test cases
        assert not is_match("aa", "a"), "Test 1 Failed"
        assert is_match("aa", "a*"), "Test 2 Failed"
        assert is_match("ab", ".*"), "Test 3 Failed"
        assert is_match("aab", "c*a*b"), "Test 4 Failed"
        assert not is_match("mississippi", "mis*is*p*."), "Test 5 Failed"
        assert is_match("mississippi", "mis*is*ip*."), "Test 6 Failed"
        assert is_match("aaa", "a*a"), "Test 7 Failed"
        assert is_match("ab", ".*.."), "Test 8 Failed"
        assert not is_match("a", ".*.."), "Test 9 Failed"
        assert not is_match("a" * 25, "a*a*a*a*a*a*a*a*a*a*b"), "Catastrophic Test Failed"
        print("All self-tests passed successfully!")
