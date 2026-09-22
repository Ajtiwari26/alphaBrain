import heapq


def merge_k_lists(lists: list[list[int]]) -> list[int]:
    """
    You are given an array of k sorted lists of integers, each sorted in ascending order.
    Merge all the lists into one sorted list and return it.
    Overall time complexity must be O(N log k) where N is the total number of elements.
    """
    if not lists:
        return []

    active_lists = [l for l in lists if l]
    if not active_lists:
        return []
    if len(active_lists) == 1:
        return list(active_lists[0])

    return list(heapq.merge(*active_lists))
