Write a production-grade, highly optimized Python implementation of Merge k Sorted Lists (LeetCode 23).

Save your implementation into a single standalone file named `merge_k_lists.py`.

### Target Function Signature
```python
def merge_k_lists(lists: list[list[int]]) -> list[int]:
    """
    You are given an array of k sorted lists of integers, each sorted in ascending order.
    Merge all the lists into one sorted list and return it.
    Overall time complexity must be O(N log k) where N is the total number of elements.
    """
```

### Specifications & Complexity
- Must run in $O(N \log k)$ time using an efficient min-heap multiway merge or divide-and-conquer merge.
- Accurately handle empty lists `[]`, lists with single elements, duplicate numbers across lists, negative integers, and disparate list lengths.
- Must comfortably pass $N = 50,000$ elements with $k = 500$ lists without exceeding time limits.

Output ONLY the complete Python code in `merge_k_lists.py` without markdown backticks or commentary so it can be written directly to file.
