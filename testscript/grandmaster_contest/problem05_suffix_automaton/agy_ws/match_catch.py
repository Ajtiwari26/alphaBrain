"""
Shortest Unique Common Substring (Codeforces 427D - Match & Catch)

This module implements a production-grade, highly optimized Suffix Automaton (SAM)
to find the length of the shortest substring that appears EXACTLY ONCE in s1
AND EXACTLY ONCE in s2. If no such substring exists, it returns -1.

Complexity:
    Time:  O((|s1| + |s2|) * log Sigma) (or O(|s1| + |s2|) average with dict transitions)
    Space: O(|s1| + |s2|)
"""

from __future__ import annotations

import sys


def shortest_unique_common_substring(s1: str, s2: str) -> int:
    """
    You are given two strings s1 and s2.
    Find the length of the shortest substring that appears EXACTLY ONCE in s1 AND EXACTLY ONCE in s2.
    If no such substring exists, return -1.
    Overall time complexity must be O((|s1| + |s2|) * log Sigma) using a Suffix Automaton (SAM)
    or Suffix Array + LCP with monotonic deque.
    """
    if not s1 or not s2:
        return -1

    # Choose two distinct sentinel delimiters not present in s1 or s2
    used = set(s1) | set(s2)
    d1: str | None = "#" if "#" not in used else None
    d2: str | None = "$" if "$" not in used and "$" != d1 else None

    if d1 is None or d2 is None:
        candidates = [chr(i) for i in range(1, 32)] + ["#", "$", "%", "&", "*", "@", "^", "~"]
        for c in candidates:
            if c not in used:
                if d1 is None:
                    d1 = c
                elif d2 is None and c != d1:
                    d2 = c
                    break

    if d1 is None or d2 is None:
        val = 0x100000
        while d1 is None or d2 is None:
            c = chr(val)
            if c not in used:
                if d1 is None:
                    d1 = c
                elif d2 is None and c != d1:
                    d2 = c
            val += 1

    # Combined string S = s1 + d1 + s2 + d2
    s_full = s1 + d1 + s2 + d2
    n = len(s_full)
    max_states = 2 * n + 2

    # Pre-allocated arrays for SAM
    length: list[int] = [0] * max_states
    link: list[int] = [-1] * max_states
    next_node: list[dict[str, int]] = [{} for _ in range(max_states)]
    cnt1: list[int] = [0] * max_states
    cnt2: list[int] = [0] * max_states

    sz = 1
    last = 0

    len_s1 = len(s1)
    split_pos1 = len_s1
    split_pos2 = len_s1 + 1 + len(s2)

    for i, ch in enumerate(s_full):
        cur = sz
        sz += 1
        length[cur] = length[last] + 1
        if i < split_pos1:
            cnt1[cur] = 1
        elif split_pos1 < i < split_pos2:
            cnt2[cur] = 1

        p = last
        while p != -1 and ch not in next_node[p]:
            next_node[p][ch] = cur
            p = link[p]

        if p == -1:
            link[cur] = 0
        else:
            q = next_node[p][ch]
            if length[p] + 1 == length[q]:
                link[cur] = q
            else:
                clone = sz
                sz += 1
                length[clone] = length[p] + 1
                next_node[clone] = next_node[q].copy()
                link[clone] = link[q]
                # Cloned state receives no direct occurrences
                while p != -1 and next_node[p].get(ch) == q:
                    next_node[p][ch] = clone
                    p = link[p]
                link[q] = clone
                link[cur] = clone

        last = cur

    # Bucket sort states by length in ascending order to establish topological order
    bucket_counts = [0] * (n + 1)
    for u in range(sz):
        bucket_counts[length[u]] += 1

    offset = [0] * (n + 1)
    total = 0
    for length_val in range(n + 1):
        offset[length_val] = total
        total += bucket_counts[length_val]

    sorted_states = [0] * sz
    for u in range(sz):
        sorted_states[offset[length[u]]] = u
        offset[length[u]] += 1

    # Propagate occurrence counts from child to parent (descending order of length)
    for i in range(sz - 1, 0, -1):
        u = sorted_states[i]
        p = link[u]
        if p != -1:
            cnt1[p] += cnt1[u]
            cnt2[p] += cnt2[u]

    # In the Suffix Automaton link tree, state u is valid if and only if cnt1[u] == 1 and cnt2[u] == 1.
    # The length of the shortest substring represented by state u is length[link[u]] + 1.
    ans = float("inf")
    for u in range(1, sz):
        if cnt1[u] == 1 and cnt2[u] == 1:
            cand = length[link[u]] + 1
            ans = min(ans, cand)

    return int(ans) if ans != float("inf") else -1


def main() -> None:
    input_data = sys.stdin.read().splitlines()
    if len(input_data) >= 2:
        s1 = input_data[0].strip()
        s2 = input_data[1].strip()
        print(shortest_unique_common_substring(s1, s2))


if __name__ == "__main__":
    main()
