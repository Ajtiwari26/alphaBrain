Write a production-grade, highly optimized Python implementation of Trapping Rain Water II (LeetCode 407).

Save your implementation into a single standalone file named `trapping_rain_3d.py`.

### Target Function Signature
```python
def trap_rain_water(height_map: list[list[int]]) -> int:
    """
    Given an m x n integer matrix height_map representing the height of each unit cell in a 2D elevation map,
    return the volume of water it can trap after raining.
    """
```

### Specifications & Complexity
- Constraints: 1 <= m, n <= 200, 0 <= height_map[i][j] <= 2 * 10^4.
- Must use a 3D Priority-Queue / Dijkstra boundary shrinking algorithm in $O(M \cdot N \log(M \cdot N))$ time.
- Push all perimeter cells into min-heap; pop minimum boundary height and flood-fill neighbors.

Output ONLY the complete Python code in `trapping_rain_3d.py` without markdown backticks or commentary so it can be written directly to file.
