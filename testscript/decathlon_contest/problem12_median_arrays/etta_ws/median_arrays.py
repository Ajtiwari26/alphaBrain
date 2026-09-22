def find_median_sorted_arrays(nums1: list[int], nums2: list[int]) -> float:
    """
    Given two sorted arrays nums1 and nums2 of size m and n respectively,
    return the median of the two sorted arrays.
    The overall run time complexity should be O(log(min(m, n))).
    """
    if len(nums1) > len(nums2):
        nums1, nums2 = nums2, nums1

    m, n = len(nums1), len(nums2)
    if m + n == 0:
        raise ValueError("Both input arrays are empty.")

    low, high = 0, m
    half_len = (m + n + 1) // 2

    while low <= high:
        i = (low + high) // 2
        j = half_len - i

        max_left_1 = nums1[i - 1] if i > 0 else float("-inf")
        min_right_1 = nums1[i] if i < m else float("inf")

        max_left_2 = nums2[j - 1] if j > 0 else float("-inf")
        min_right_2 = nums2[j] if j < n else float("inf")

        if max_left_1 <= min_right_2 and max_left_2 <= min_right_1:
            if (m + n) % 2 == 1:
                return float(max(max_left_1, max_left_2))
            else:
                return (
                    max(max_left_1, max_left_2) + min(min_right_1, min_right_2)
                ) / 2.0
        elif max_left_1 > min_right_2:
            high = i - 1
        else:
            low = i + 1

    raise ValueError("Input arrays are not sorted.")
