from bisect import bisect_left


def max_envelopes(envelopes: list[list[int]]) -> int:
    """
    You are given a 2D array of integers envelopes where envelopes[i] = [w_i, h_i] represents the width and height of an envelope.
    One envelope can fit into another if and only if both the width and height of one envelope are strictly greater than the other envelope.
    Return the maximum number of envelopes you can Russian doll (i.e., put one inside the other).
    Note: You cannot rotate an envelope.

    Time Complexity: O(N log N)
    Space Complexity: O(N)
    """
    if not envelopes:
        return 0

    # Sort envelopes: width ascending, height descending for equal widths.
    # Sorting height descending ensures that envelopes with the same width
    # cannot be included in the same strictly increasing height sequence (LIS).
    envelopes.sort(key=lambda x: (x[0], -x[1]))

    # Longest Increasing Subsequence (LIS) on heights using patience sorting / binary search
    tails = []
    for _, h in envelopes:
        idx = bisect_left(tails, h)
        if idx == len(tails):
            tails.append(h)
        else:
            tails[idx] = h

    return len(tails)
