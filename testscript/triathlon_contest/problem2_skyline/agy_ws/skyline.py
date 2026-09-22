"""
Production-grade implementation of The Skyline Problem (LeetCode 218).

This module provides an optimal O(N log N) sweep-line algorithm using a max-heap
with lazy deletion to compute the 2D silhouette contour of building collections.
"""

import math
from collections import defaultdict
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
        - Consecutive horizontal lines of equal height must be merged (no adjacent key points with identical y).
        - The last point must end at height 0.
        - If buildings is empty, return [].
    """
    if not buildings:
        return []

    # Map each starting x-coordinate to a list of (height, right_endpoint)
    starts: dict[int, list[tuple[int, int]]] = defaultdict(list)
    critical_x_coords: set[int] = set()

    for left, right, height in buildings:
        starts[left].append((height, right))
        critical_x_coords.add(left)
        critical_x_coords.add(right)

    # Sort all unique critical x-coordinates where building boundaries occur
    sorted_x = sorted(critical_x_coords)

    # Max-heap storing (-height, right_endpoint).
    # Initialized with a sentinel for ground level (height=0) extending to infinity.
    # Negating height allows min-heap (heapq) to function as a max-heap.
    max_heap: list[tuple[int, float]] = [(0, math.inf)]
    skyline: list[list[int]] = []
    current_height = 0

    for x in sorted_x:
        # 1. Lazily pop buildings that have ended at or before current x
        while max_heap[0][1] <= x:
            heappop(max_heap)

        # 2. Add all buildings starting at current x
        if x in starts:
            for height, right in starts[x]:
                heappush(max_heap, (-height, right))

        # 3. Check if the current max height has changed
        new_height = -max_heap[0][0]
        if new_height != current_height:
            skyline.append([x, new_height])
            current_height = new_height

    return skyline


if __name__ == "__main__":
    # Quick self-verification on standard LeetCode example
    sample_buildings = [
        [2, 9, 10],
        [3, 7, 15],
        [5, 12, 12],
        [15, 20, 10],
        [19, 24, 8],
    ]
    expected_output = [
        [2, 10],
        [3, 15],
        [7, 12],
        [12, 0],
        [15, 10],
        [20, 8],
        [24, 0],
    ]
    result = get_skyline(sample_buildings)
    assert result == expected_output, f"Expected {expected_output}, got {result}"
    print("Self-test passed successfully!")
