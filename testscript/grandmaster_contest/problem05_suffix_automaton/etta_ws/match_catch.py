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

    # Find two delimiter characters not present in s1 or s2
    s_set = set(s1) | set(s2)
    d1, d2 = None, None
    for code in range(1, 0x10FFFF):
        if 0xD800 <= code <= 0xDFFF:
            continue
        c = chr(code)
        if c not in s_set:
            if d1 is None:
                d1 = c
            elif d2 is None:
                d2 = c
                break

    len1 = len(s1)
    len2 = len(s2)
    S = s1 + d1 + s2 + d2
    N = len(S)

    # Pre-allocate SAM arrays
    max_states = 2 * N + 2
    st_len = [0] * max_states
    st_link = [0] * max_states
    st_next = [{} for _ in range(max_states)]
    cnt1 = [0] * max_states
    cnt2 = [0] * max_states

    st_link[0] = -1
    sz = 1
    last = 0

    # Build Suffix Automaton
    for i, c in enumerate(S):
        cur = sz
        sz += 1
        st_len[cur] = st_len[last] + 1

        if i < len1:
            cnt1[cur] = 1
        elif len1 < i <= len1 + len2:
            cnt2[cur] = 1

        p = last
        while p != -1 and c not in st_next[p]:
            st_next[p][c] = cur
            p = st_link[p]

        if p == -1:
            st_link[cur] = 0
        else:
            q = st_next[p][c]
            if st_len[p] + 1 == st_len[q]:
                st_link[cur] = q
            else:
                clone = sz
                sz += 1
                st_len[clone] = st_len[p] + 1
                st_next[clone] = st_next[q].copy()
                st_link[clone] = st_link[q]
                cnt1[clone] = 0
                cnt2[clone] = 0

                while p != -1 and st_next[p].get(c) == q:
                    st_next[p][c] = clone
                    p = st_link[p]

                st_link[q] = clone
                st_link[cur] = clone

        last = cur

    # Topological sort by state max-length descending for DP on link tree
    order = list(range(sz))
    order.sort(key=lambda u: st_len[u], reverse=True)

    for u in order:
        p = st_link[u]
        if p != -1:
            cnt1[p] += cnt1[u]
            cnt2[p] += cnt2[u]

    # Find minimum length of substring with cnt1[u] == 1 and cnt2[u] == 1
    ans = float("inf")
    for u in range(1, sz):
        if cnt1[u] == 1 and cnt2[u] == 1:
            min_len = st_len[st_link[u]] + 1
            if min_len < ans:
                ans = min_len

    return ans if ans != float("inf") else -1


if __name__ == "__main__":
    input_data = sys.stdin.read().splitlines()
    if len(input_data) >= 2:
        s1 = input_data[0].strip()
        s2 = input_data[1].strip()
        print(shortest_unique_common_substring(s1, s2))
