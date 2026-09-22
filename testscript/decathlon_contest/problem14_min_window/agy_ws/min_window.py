"""
Production-grade, highly optimized implementation of Minimum Window Substring (LeetCode 76).
"""

from collections import Counter


def min_window(s: str, t: str) -> str:
    """
    Given two strings s and t of lengths m and n respectively, return the minimum window substring
    of s such that every character in t (including duplicates) is included in the window.
    If there is no such substring, return the empty string "".
    If there are multiple such minimum-length substrings, return the one that occurs first in s.
    The overall run time complexity must be O(m + n).
    """
    len_s = len(s)
    len_t = len(t)

    # Fast pruning on trivial edge cases
    if len_s < len_t or len_t == 0:
        return ""

    if s == t:
        return s

    if len_t == 1:
        return t if t in s else ""

    # Check if inputs are standard ASCII for zero-overhead byte array indexing
    try:
        s_bytes = s.encode("ascii")
        t_bytes = t.encode("ascii")
        is_ascii = True
    except UnicodeEncodeError:
        is_ascii = False

    if is_ascii:
        need = [0] * 128
        for b in t_bytes:
            need[b] += 1

        missing = len_t
        min_len = len_s + 1
        best_start = 0
        best_end = 0
        l = 0

        for r, b in enumerate(s_bytes):
            if need[b] > 0:
                missing -= 1
            need[b] -= 1

            if missing == 0:
                # Contract from left while redundant characters exist
                while need[s_bytes[l]] < 0:
                    need[s_bytes[l]] += 1
                    l += 1

                window_len = r - l + 1
                if window_len < min_len:
                    min_len = window_len
                    best_start = l
                    best_end = r + 1
                    # Theoretical minimum window length reached; earliest match guaranteed
                    if min_len == len_t:
                        return s[best_start:best_end]

                # Advance left pointer to search for next candidate window
                need[s_bytes[l]] += 1
                missing += 1
                l += 1

        return s[best_start:best_end] if min_len <= len_s else ""

    # Unicode fallback path using hash map
    need = Counter(t)
    missing = len_t
    min_len = len_s + 1
    best_start = 0
    best_end = 0
    l = 0

    for r, ch in enumerate(s):
        if need[ch] > 0:
            missing -= 1
        need[ch] -= 1

        if missing == 0:
            while need[s[l]] < 0:
                need[s[l]] += 1
                l += 1

            window_len = r - l + 1
            if window_len < min_len:
                min_len = window_len
                best_start = l
                best_end = r + 1
                if min_len == len_t:
                    return s[best_start:best_end]

            need[s[l]] += 1
            missing += 1
            l += 1

    return s[best_start:best_end] if min_len <= len_s else ""
