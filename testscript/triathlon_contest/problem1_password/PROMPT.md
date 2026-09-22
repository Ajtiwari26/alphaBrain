Write a production-grade, highly optimized Python implementation of the Strong Password Checker algorithm (LeetCode 420).

Save your implementation into a single standalone file named `password_checker.py`.

### Target Function Signature
```python
def strong_password_checker(password: str) -> int:
    """
    Given a string password, return the minimum number of steps to make password strong.
    A step is inserting one character, deleting one character, or replacing one character.
    """
```

### Specifications & Requirements
A password is considered strong if:
1. **Length Requirement**: It has at least 6 characters and at most 20 characters.
2. **Character Categories**: It contains at least one lowercase letter, at least one uppercase letter, and at least one digit.
3. **Repetition Rule**: It does not contain three repeating characters in a row (i.e., `"..."`, `"aaa"`, `"111"` are forbidden).

### Goal
Calculate and return the **minimum number of operations** (insert, delete, or replace) required to transform the given password into a strong password.

Output ONLY the complete Python code in `password_checker.py` without markdown backticks or commentary so it can be written directly to file.
