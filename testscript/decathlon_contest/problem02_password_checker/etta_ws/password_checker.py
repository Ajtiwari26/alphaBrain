def strong_password_checker(password: str) -> int:
    """
    Calculate the minimum number of steps (insert, delete, replace) to make password strong:
    1. Length between 6 and 20.
    2. At least 1 lowercase, 1 uppercase, 1 digit.
    3. No three consecutive identical characters.
    """
    n = len(password)

    has_lower = False
    has_upper = False
    has_digit = False

    runs = []
    i = 0
    while i < n:
        c = password[i]
        if not has_lower and c.islower():
            has_lower = True
        elif not has_upper and c.isupper():
            has_upper = True
        elif not has_digit and c.isdigit():
            has_digit = True

        j = i + 1
        while j < n and password[j] == c:
            j += 1

        length = j - i
        if length >= 3:
            runs.append(length)
        i = j

    missing_types = (0 if has_lower else 1) + (0 if has_upper else 1) + (0 if has_digit else 1)

    if n < 6:
        return max(6 - n, missing_types)

    replace_count = sum(length // 3 for length in runs)

    if n <= 20:
        return max(replace_count, missing_types)

    deletions = n - 20

    # Step 1: Use deletions to reduce runs where length % 3 == 0 (1 deletion saves 1 replacement)
    for k in range(len(runs)):
        if deletions > 0 and runs[k] % 3 == 0:
            runs[k] -= 1
            deletions -= 1
            replace_count -= 1

    # Step 2: Use deletions to reduce runs where length % 3 == 1 (2 deletions save 1 replacement)
    for k in range(len(runs)):
        if deletions >= 2 and runs[k] % 3 == 1:
            runs[k] -= 2
            deletions -= 2
            replace_count -= 1

    # Step 3: Any remaining deletions reduce replace_count by 1 for every 3 deletions spent
    replace_count = max(0, replace_count - deletions // 3)

    return (n - 20) + max(replace_count, missing_types)


if __name__ == "__main__":
    assert strong_password_checker("a") == 5
    assert strong_password_checker("aA1") == 3
    assert strong_password_checker("1337C0d3") == 0
    assert strong_password_checker("aaa123") == 1
    assert strong_password_checker("AAAAAAAAAAAAAAAAAAAAA") == 7
    print("All tests passed successfully.")
