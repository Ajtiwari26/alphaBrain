import heapq


def get_skyline(buildings: list[list[int]]) -> list[list[int]]:
    """
    Return the outer contour silhouette key points [x, y] sorted by x-coordinate.
    Consecutive points of equal height must be merged. Last point must end at height 0.

    Optimized Sweep-Line Algorithm with Lazy Heap Deletion (O(N log N) time, O(N) space).
    """
    if not buildings:
        return []

    # Generate critical events:
    # Building start: (l, -h, r)
    # Building end:   (r, 0, 0)
    events = []
    for l, r, h in buildings:
        events.append((l, -h, r))
        events.append((r, 0, 0))

    # Event sorting logic:
    # 1. Sort by X-coordinate ascending.
    # 2. For same X:
    #    - Start events (-h < 0) are processed before end events (0).
    #    - Taller start events (more negative -h) are processed before shorter ones.
    events.sort()

    # Max-heap (simulated via min-heap with negative heights) storing (-height, end_x)
    # Seeded with base ground level ending at infinity
    hp = [(0, float("inf"))]
    skyline = []
    prev_max_h = 0

    for x, neg_h, r in events:
        # Purge expired buildings from top of heap (lazy deletion)
        while hp[0][1] <= x:
            heapq.heappop(hp)

        # If it's a building start event, push to heap
        if neg_h < 0:
            heapq.heappush(hp, (neg_h, r))

        # Peak height at the current X coordinate
        curr_max_h = -hp[0][0]

        # Record keypoint whenever peak height changes
        if curr_max_h != prev_max_h:
            skyline.append([x, curr_max_h])
            prev_max_h = curr_max_h

    return skyline
