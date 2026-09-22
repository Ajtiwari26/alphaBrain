def strong_password_checker(password: str) -> int:
    """
    Given a string password, return the minimum number of steps to make password strong.
    A step is inserting one character, deleting one character, or replacing one character.
    """
    n = len(password)
    
    # Determine missing character types
    has_lower = False
    has_upper = False
    has_digit = False
    
    for char in password:
        if char.islower():
            has_lower = True
        elif char.isupper():
            has_upper = True
        elif char.isdigit():
            has_digit = True
            
    missing_types = (not has_lower) + (not has_upper) + (not has_digit)
    
    # Case 1: Password length is less than 6
    if n < 6:
        return max(6 - n, missing_types)
    
    # Find all contiguous sequence runs of repeating characters of length >= 3
    runs = []
    i = 0
    while i < n:
        j = i
        while j < n and password[j] == password[i]:
            j += 1
        length = j - i
        if length >= 3:
            runs.append(length)
        i = j
        
    replace_count = sum(length // 3 for length in runs)
    
    # Case 2: Password length is between 6 and 20 (inclusive)
    if n <= 20:
        return max(replace_count, missing_types)
    
    # Case 3: Password length is greater than 20
    deletions_needed = n - 20
    d = deletions_needed
    
    # Step 1: Use 1 deletion on runs where length % 3 == 0 to save 1 replacement
    for idx in range(len(runs)):
        if d > 0 and runs[idx] % 3 == 0:
            runs[idx] -= 1
            d -= 1
            replace_count -= 1
            
    # Step 2: Use 2 deletions on runs where length % 3 == 1 to save 1 replacement
    for idx in range(len(runs)):
        if d >= 2 and runs[idx] % 3 == 1:
            runs[idx] -= 2
            d -= 2
            replace_count -= 1
            
    # Step 3: Use 3 deletions on any remaining runs to save replacements
    for idx in range(len(runs)):
        if d >= 3 and runs[idx] >= 3:
            k = min(d // 3, runs[idx] // 3)
            runs[idx] -= 3 * k
            d -= 3 * k
            replace_count -= k
            
    return deletions_needed + max(replace_count, missing_types)
