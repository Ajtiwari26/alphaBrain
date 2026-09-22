def strong_password_checker(password: str) -> int:
    """
    Calculate the minimum number of steps (insert, delete, replace) to make password strong:
    1. Length between 6 and 20.
    2. At least 1 lowercase, 1 uppercase, 1 digit.
    3. No three consecutive identical characters.
    """
    n = len(password)

    # 1. Missing character categories
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    missing_types = (0 if has_lower else 1) + (0 if has_upper else 1) + (0 if has_digit else 1)

    # 2. Identify repeating character runs of length >= 3
    runs: list[int] = []
    i = 0
    while i < n:
        j = i
        while j < n and password[j] == password[i]:
            j += 1
        run_len = j - i
        if run_len >= 3:
            runs.append(run_len)
        i = j

    # Case 1: Length < 6
    # We must insert characters to reach at least length 6 (total: 6 - n).
    # Any insertion can be strategically chosen to fulfill a missing category
    # and break any repeating run (since maximum possible run length is <= 5).
    if n < 6:
        return max(6 - n, missing_types)

    # Case 2: 6 <= Length <= 20
    # Length is already valid. Only replacements are needed to break runs of >= 3.
    # Each replacement can simultaneously supply a missing character type.
    if n <= 20:
        replace_needed = sum(k // 3 for k in runs)
        return max(replace_needed, missing_types)

    # Case 3: Length > 20
    # Length is too large. We MUST delete (n - 20) characters.
    # Deletions can be prioritized greedily to eliminate the need for replacements:
    # - A run with k % 3 == 0 needs 1 deletion to reduce replacements needed by 1 (efficiency 1:1).
    # - A run with k % 3 == 1 needs 2 deletions to reduce replacements needed by 1 (efficiency 2:1).
    # - Any remaining run needs 3 deletions to reduce replacements needed by 1 (efficiency 3:1).
    delete_needed = n - 20
    delete_count = delete_needed

    # Phase 1: k % 3 == 0 (spend 1 deletion per run)
    for idx in range(len(runs)):
        if delete_count >= 1 and runs[idx] % 3 == 0:
            runs[idx] -= 1
            delete_count -= 1

    # Phase 2: k % 3 == 1 (spend 2 deletions per run)
    for idx in range(len(runs)):
        if delete_count >= 2 and runs[idx] % 3 == 1:
            runs[idx] -= 2
            delete_count -= 2

    # Phase 3: Spend remaining deletions in batches of 3
    replace_needed = sum(k // 3 for k in runs)
    if delete_count >= 3 and replace_needed > 0:
        reductions = min(delete_count // 3, replace_needed)
        replace_needed -= reductions
        delete_count -= reductions * 3

    # Any remaining replacements can simultaneously satisfy missing character types.
    return delete_needed + max(replace_needed, missing_types)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        pwd = sys.argv[1]
        print(strong_password_checker(pwd))
    else:
        # Quick verification of canonical test cases
        test_cases = [
            ("a", 5),
            ("aA1", 3),
            ("1337C0d3", 0),
            ("aaa111", 2),
            ("....................", 6),
            ("aaaaaaaAAAAAA6666bbb", 6),
            ("aaaaaaaAAAAAA6666bbbb", 6),
            ("ABABABABABABABABABAB1", 2),
            ("bbaaaaaaaaaaaaaaacccccc", 8),
        ]
        for pwd, expected in test_cases:
            res = strong_password_checker(pwd)
            assert res == expected, f"Failed for '{pwd}': got {res}, expected {expected}"
        print("All canonical test cases passed successfully.")
