def min_window(s: str, t: str) -> str:
    """
    Given two strings s and t of lengths m and n respectively, return the minimum window substring
    of s such that every character in t (including duplicates) is included in the window.
    If there is no such substring, return the empty string "".
    If there are multiple such minimum-length substrings, return the one that occurs first in s.
    The overall run time complexity must be O(m + n).
    """
    m, n = len(s), len(t)
    if m < n or n == 0:
        return ""

    max_s = ord(max(s))
    max_t = ord(max(t))

    # Fast path for ASCII / Latin-1 characters (< 256)
    if max_s < 256 and max_t < 256:
        s_bytes = s.encode("latin-1")
        t_bytes = t.encode("latin-1")

        counts = [0] * 256
        for b in t_bytes:
            counts[b] += 1

        missing = n
        min_len = m + 1
        start_idx = 0
        left = 0

        for right, b in enumerate(s_bytes):
            if counts[b] > 0:
                missing -= 1
            counts[b] -= 1

            while missing == 0:
                current_len = right - left + 1
                if current_len < min_len:
                    min_len = current_len
                    start_idx = left

                left_b = s_bytes[left]
                if counts[left_b] == 0:
                    missing += 1
                counts[left_b] += 1
                left += 1

        return s[start_idx : start_idx + min_len] if min_len <= m else ""

    # General Unicode path for characters with code points >= 256
    target_counts = {}
    for char in t:
        target_counts[char] = target_counts.get(char, 0) + 1

    missing = n
    min_len = m + 1
    start_idx = 0
    left = 0

    for right, char in enumerate(s):
        if char in target_counts:
            if target_counts[char] > 0:
                missing -= 1
            target_counts[char] -= 1

        while missing == 0:
            current_len = right - left + 1
            if current_len < min_len:
                min_len = current_len
                start_idx = left

            left_char = s[left]
            if left_char in target_counts:
                if target_counts[left_char] == 0:
                    missing += 1
                target_counts[left_char] += 1
            left += 1

    return s[start_idx : start_idx + min_len] if min_len <= m else ""
