import heapq


def trap_rain_water(height_map: list[list[int]]) -> int:
    """
    Given an m x n integer matrix height_map representing the height of each unit cell in a 2D elevation map,
    return the volume of water it can trap after raining.

    Uses a Min-Heap (Dijkstra-like boundary shrinking algorithm).
    Time Complexity: O(M * N * log(M * N))
    Space Complexity: O(M * N)
    """
    if not height_map or not height_map[0]:
        return 0

    m, n = len(height_map), len(height_map[0])
    if m < 3 or n < 3:
        return 0

    visited = [[False] * n for _ in range(m)]
    heap = []

    # Add all outer boundary cells to the min-heap
    for r in range(m):
        for c in (0, n - 1):
            heap.append((height_map[r][c], r, c))
            visited[r][c] = True

    for c in range(1, n - 1):
        for r in (0, m - 1):
            heap.append((height_map[r][c], r, c))
            visited[r][c] = True

    heapq.heapify(heap)

    total_water = 0
    max_boundary = 0
    directions = ((-1, 0), (1, 0), (0, -1), (0, 1))

    # Process boundary shrinking inward
    while heap:
        height, r, c = heapq.heappop(heap)
        if height > max_boundary:
            max_boundary = height

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < m and 0 <= nc < n and not visited[nr][nc]:
                visited[nr][nc] = True
                neighbor_height = height_map[nr][nc]
                if neighbor_height < max_boundary:
                    total_water += max_boundary - neighbor_height
                heapq.heappush(heap, (neighbor_height, nr, nc))

    return total_water


if __name__ == "__main__":
    # Quick sanity check
    test_grid = [
        [1, 4, 3, 1, 3, 2],
        [3, 2, 1, 3, 2, 4],
        [2, 3, 3, 2, 3, 1]
    ]
    assert trap_rain_water(test_grid) == 4
