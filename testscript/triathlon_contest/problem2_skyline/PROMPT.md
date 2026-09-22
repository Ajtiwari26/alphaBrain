Write a production-grade, highly optimized Python implementation of The Skyline Problem (LeetCode 218).

Save your implementation into a single standalone file named `skyline.py`.

### Target Function Signature
```python
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
```

### Specifications & Requirements
1. **Sweep-Line Algorithm**: Must efficiently handle overlapping intervals using an active max-heap, segment tree, or balanced tree in $O(N \log N)$ time.
2. **Boundary Collisions**: Must correctly handle:
   - Buildings with identical start coordinates and different heights.
   - Buildings with identical end coordinates and different heights.
   - Buildings where one starts exactly where another ends.
   - Buildings completely enclosed inside taller buildings.
3. **No Redundant Points**: Never output two consecutive points with the same height.

Output ONLY the complete Python code in `skyline.py` without markdown backticks or commentary so it can be written directly to file.
