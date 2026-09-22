"""
Production-grade, highly optimized Python implementation of The Skyline Problem (LeetCode 218).

Problem Description:
    A city's skyline is the outer contour of the silhouette formed by all the buildings
    when viewed from a distance. Given the locations and heights of all the buildings,
    return the skyline formed by these buildings collectively.

    The geometric information for each building is given in the array buildings where:
    buildings[i] = [left_i, right_i, height_i]:
    - left_i: x-coordinate of the left edge of the i-th building.
    - right_i: x-coordinate of the right edge of the i-th building.
    - height_i: height of the i-th building.

    The skyline should be represented as a list of "key points" [x, y] sorted by their
    x-coordinate in the form [[x1, y1], [x2, y2], ...].
    Key points are the left endpoints of horizontal line segments.
    Consecutive horizontal lines of equal height must be merged.
    The last key point must end at height 0.

Algorithm & Complexity:
    - Sweep-line algorithm with a max-heap (using negative heights in Python's min-heap heapq).
    - Collect all unique critical x-coordinates (building left and right boundaries).
    - Group building start events by left x-coordinate.
    - At each critical x-coordinate in ascending order:
        1. Lazily prune ended buildings (right <= current x) from the top of the heap.
        2. Push all new buildings starting at current x into the heap.
        3. Sample the current maximum active height.
        4. If max height changed compared to the previous key point, record [x, new_height].
    - Time Complexity: O(N log N) where N is the number of buildings.
    - Space Complexity: O(N) auxiliary space.
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict
from heapq import heappop, heappush


def get_skyline(buildings: list[list[int]]) -> list[list[int]]:
    """
    Return the outer contour silhouette key points [x, y] sorted by x-coordinate.
    Consecutive points of equal height must be merged. Last point must end at height 0.
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
    max_heap: list[tuple[int, int | float]] = [(0, math.inf)]
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


class Solution:
    """LeetCode compatible class wrapper for The Skyline Problem."""

    def getSkyline(self, buildings: list[list[int]]) -> list[list[int]]:
        return get_skyline(buildings)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        import json

        try:
            raw_input = " ".join(sys.argv[1:])
            data = json.loads(raw_input)
            print(get_skyline(data))
        except (json.JSONDecodeError, TypeError, ValueError) as err:
            print(f"Error parsing input: {err}", file=sys.stderr)
            sys.exit(1)
    else:
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
