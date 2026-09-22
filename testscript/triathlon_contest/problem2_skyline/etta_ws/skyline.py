from heapq import heappop, heappush


def get_skyline(buildings: list[list[int]]) -> list[list[int]]:
    """
    A city's skyline is the outer contour of the silhouette formed by all the buildings
    when viewed from a distance. Given the locations and heights of all buildings,
    return the skyline formed by these buildings collectively.

    Parameters:
        buildings: list of [left_i, right_i, height_i] where 0 <= left_i < right_i <= 2^31 - 1
                   and 1 <= height_i <= 2^31 - 1.

    Returns:
        list of [x, y] key points forming the skyline, sorted by x-coordinate.
        - Consecutive horizontal lines of equal height must be merged.
        - The last point must end at height 0.
        - If buildings is empty, return [].
    """
    if not buildings:
        return []

    # Create events:
    # Start event: (x, -height) -> negative height ensures taller buildings are processed first
    # End event:   (x, height)  -> positive height ensures start events are processed before end events
    events = [(l, -h) for l, r, h in buildings]
    events.extend((r, h) for l, r, h in buildings)
    events.sort()

    # Active max-heap storing negative heights; initialized with 0 for ground level
    hp = [0]
    # Lazy deletion table for heights of buildings that have ended
    forget = {}
    result = []
    prev_max = 0

    for x, h in events:
        if h < 0:
            # Start event: push height (-h is negative)
            heappush(hp, h)
        else:
            # End event: record pending removal for height (-h)
            neg_h = -h
            forget[neg_h] = forget.get(neg_h, 0) + 1

        # Purge stale max values from the top of the heap
        while hp:
            top = hp[0]
            count = forget.get(top, 0)
            if count > 0:
                if count == 1:
                    del forget[top]
                else:
                    forget[top] = count - 1
                heappop(hp)
            else:
                break

        curr_max = -hp[0]
        # Emit key point only when the visible skyline height changes
        if curr_max != prev_max:
            result.append([x, curr_max])
            prev_max = curr_max

    return result
