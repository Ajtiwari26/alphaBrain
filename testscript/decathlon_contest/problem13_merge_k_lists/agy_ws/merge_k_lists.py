"""
Merge k Sorted Lists (LeetCode 23)

Production-grade, highly optimized Python implementation of Merge k Sorted Lists
running in strict O(N log k) time complexity and O(k) auxiliary heap space.
"""

from __future__ import annotations

import heapq
import json
import sys


def merge_k_lists(lists: list[list[int]]) -> list[int]:
    """
    You are given an array of k sorted lists of integers, each sorted in ascending order.
    Merge all the lists into one sorted list and return it.
    Overall time complexity must be O(N log k) where N is the total number of elements.

    Algorithm & Complexity:
        - Let k = len(lists) and N = sum(len(lst) for lst in lists).
        - A min-heap maintains at most k elements (one head element from each active list).
        - Extracting the minimum element and advancing the corresponding list iterator takes O(log k).
        - Total operations: N insertions and N extractions in a heap of size <= k -> O(N log k).
        - Auxiliary Space: O(k) working space for the min-heap.
        - CPython's heapq.merge implements this multiway merge algorithm natively in C (_heapqmodule.c),
          eliminating Python interpreter overhead while strictly adhering to O(N log k) time and O(k) space.

    Edge Cases Handled:
        - lists is empty: [] -> []
        - lists with empty lists: [[], [], []] -> []
        - Single list: [[1, 2, 3]] -> [1, 2, 3]
        - Negative integers, zeros, large positive numbers
        - Lists of disparate lengths
        - Duplicate numbers across multiple lists
    """
    if not lists:
        return []

    if len(lists) == 1:
        return list(lists[0])

    # Filter out empty lists to avoid unnecessary iterator/heap overhead
    active_lists = [lst for lst in lists if lst]
    if not active_lists:
        return []
    if len(active_lists) == 1:
        return list(active_lists[0])

    return list(heapq.merge(*active_lists))


def merge_k_lists_heap(lists: list[list[int]]) -> list[int]:
    """
    Explicit min-heap implementation of multiway merge.
    Maintains a min-heap of size at most k storing tuples:
        (val, list_index, element_index)

    Because list_index is unique for each sublist, tuples are strictly ordered
    without ever comparing element_index or encountering non-comparable tie-breaks.

    Time Complexity: O(N log k)
    Auxiliary Space Complexity: O(k)
    """
    if not lists:
        return []

    heap: list[tuple[int, int, int]] = []
    for list_idx, lst in enumerate(lists):
        if lst:
            heap.append((lst[0], list_idx, 0))

    heapq.heapify(heap)
    result: list[int] = []

    while heap:
        val, list_idx, elem_idx = heap[0]
        result.append(val)
        next_elem_idx = elem_idx + 1
        target_list = lists[list_idx]
        if next_elem_idx < len(target_list):
            heapq.heapreplace(heap, (target_list[next_elem_idx], list_idx, next_elem_idx))
        else:
            heapq.heappop(heap)

    return result


def merge_k_lists_divide_and_conquer(lists: list[list[int]]) -> list[int]:
    """
    Pairwise divide-and-conquer implementation of merge k sorted lists.
    Merges lists in pairs across ceil(log2(k)) levels.

    Time Complexity: O(N log k)
    Auxiliary Space Complexity: O(N)
    """
    if not lists:
        return []

    current: list[list[int]] = [lst for lst in lists if lst]
    if not current:
        return []

    def _merge_two(l1: list[int], l2: list[int]) -> list[int]:
        merged: list[int] = []
        i = j = 0
        n1, n2 = len(l1), len(l2)
        while i < n1 and j < n2:
            if l1[i] <= l2[j]:
                merged.append(l1[i])
                i += 1
            else:
                merged.append(l2[j])
                j += 1
        if i < n1:
            merged.extend(l1[i:])
        if j < n2:
            merged.extend(l2[j:])
        return merged

    while len(current) > 1:
        next_level: list[list[int]] = []
        for i in range(0, len(current), 2):
            if i + 1 < len(current):
                next_level.append(_merge_two(current[i], current[i + 1]))
            else:
                next_level.append(current[i])
        current = next_level

    return current[0]


class Solution:
    """LeetCode compatible class wrapper for Merge k Sorted Lists (LeetCode 23)."""

    def mergeKLists(self, lists: list[list[int]]) -> list[int]:
        """LeetCode entry point."""
        return merge_k_lists(lists)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            parsed_lists = json.loads(sys.argv[1])
            if not isinstance(parsed_lists, list):
                raise TypeError("Input must be a JSON array of arrays.")
            print(merge_k_lists(parsed_lists))
        except (json.JSONDecodeError, TypeError, ValueError) as err:
            print(f"Error parsing CLI input: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        # Canonical self-tests
        assert merge_k_lists([[1, 4, 5], [1, 3, 4], [2, 6]]) == [1, 1, 2, 3, 4, 4, 5, 6]
        assert merge_k_lists([]) == []
        assert merge_k_lists([[]]) == []
        assert merge_k_lists([[], [], []]) == []
        assert merge_k_lists([[-10, -5, 0], [-20, -1, 4], [-15, 2]]) == [-20, -15, -10, -5, -1, 0, 2, 4]
        assert merge_k_lists([[1], [0]]) == [0, 1]

        # Verify equivalence with explicit heap and divide-and-conquer
        sample = [[1, 4, 5], [1, 3, 4], [2, 6], [-5, 10], []]
        assert merge_k_lists(sample) == merge_k_lists_heap(sample)
        assert merge_k_lists(sample) == merge_k_lists_divide_and_conquer(sample)

        print("Self-tests passed successfully!")
