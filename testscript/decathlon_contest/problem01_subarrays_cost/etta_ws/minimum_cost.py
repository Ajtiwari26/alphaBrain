import heapq


def minimum_cost(nums: list[int], k: int, dist: int) -> int:
    """
    You are given an integer array nums of length n, and two integers k and dist.
    You must divide nums into k contiguous subarrays.
    The cost of dividing nums is the sum of the first elements of each of the k subarrays.
    The first element of the first subarray is always nums[0].
    The distance between the start index of the second subarray and the start index of the
    k-th subarray must be at most dist. That is, if the start indices of the subarrays are
    0 = i_0 < i_1 < i_2 < ... < i_{k-1}, then i_{k-1} - i_1 <= dist.
    Return the minimum possible cost.
    """
    n = len(nums)
    m = k - 1
    if m == 0:
        return nums[0]

    small = []  # max-heap storing (-val, idx)
    large = []  # min-heap storing (val, idx)
    in_small = bytearray(n)

    small_sum = 0
    small_size = 0
    ans = float('inf')

    heappush = heapq.heappush
    heappop = heapq.heappop

    for i in range(1, n):
        left_bound = i - dist
        out_idx = i - dist - 1

        # 1. Remove outgoing element from sliding window
        if out_idx >= 1 and in_small[out_idx]:
            in_small[out_idx] = 0
            small_sum -= nums[out_idx]
            small_size -= 1

        # 2. Add nums[i] to small
        val = nums[i]
        heappush(small, (-val, i))
        in_small[i] = 1
        small_sum += val
        small_size += 1

        # 3. If small exceeds target size m, move max element of small to large
        if small_size > m:
            while small and (small[0][1] < left_bound or not in_small[small[0][1]]):
                heappop(small)
            neg_v, idx = heappop(small)
            in_small[idx] = 0
            small_sum -= (-neg_v)
            small_size -= 1
            heappush(large, (-neg_v, idx))

        # 4. If small has fewer than m elements, top up from large
        while small_size < m:
            while large and (large[0][1] < left_bound or in_small[large[0][1]]):
                heappop(large)
            if not large:
                break
            v, idx = heappop(large)
            in_small[idx] = 1
            small_sum += v
            small_size += 1
            heappush(small, (-v, idx))

        # 5. Ensure max(small) <= min(large)
        while small and (small[0][1] < left_bound or not in_small[small[0][1]]):
            heappop(small)
        while large and (large[0][1] < left_bound or in_small[large[0][1]]):
            heappop(large)

        if small and large and -small[0][0] > large[0][0]:
            neg_v_s, idx_s = heappop(small)
            v_l, idx_l = heappop(large)

            in_small[idx_s] = 0
            in_small[idx_l] = 1

            small_sum += v_l - (-neg_v_s)

            heappush(large, (-neg_v_s, idx_s))
            heappush(small, (-v_l, idx_l))

        # 6. Record minimum cost if we have m elements in small
        if small_size == m:
            cost = nums[0] + small_sum
            if cost < ans:
                ans = cost

    return ans
