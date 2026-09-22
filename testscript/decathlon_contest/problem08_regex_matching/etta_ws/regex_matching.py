def is_match(s: str, p: str) -> bool:
    """
    Given an input string s and a pattern p, implement regular expression matching with support for '.' and '*' where:
    - '.' Matches any single character.
    - '*' Matches zero or more of the preceding element.
    The matching should cover the entire input string (not partial).
    """
    m, n = len(s), len(p)
    
    # dp[j] will store match result for current s prefix and p[:j]
    dp = [False] * (n + 1)
    dp[0] = True
    
    # Initialize base case for empty string s (i = 0)
    for j in range(2, n + 1):
        if p[j - 1] == '*':
            dp[j] = dp[j - 2]
            
    for i in range(1, m + 1):
        prev_diag = dp[0]  # Stores dp[i-1][j-1]
        dp[0] = False      # Non-empty string s[:i] cannot match empty pattern
        
        char_s = s[i - 1]
        for j in range(1, n + 1):
            temp = dp[j]  # Stores dp[i-1][j] before updating dp[j]
            char_p = p[j - 1]
            
            if char_p == '*':
                prev_p = p[j - 2]
                zero_match = dp[j - 2]  # dp[i][j-2]
                one_or_more_match = (prev_p == '.' or prev_p == char_s) and temp  # dp[i-1][j]
                dp[j] = zero_match or one_or_more_match
            else:
                dp[j] = (char_p == '.' or char_p == char_s) and prev_diag
                
            prev_diag = temp
            
    return dp[n]


if __name__ == "__main__":
    # Smoke tests
    assert is_match("aa", "a") is False
    assert is_match("aa", "a*") is True
    assert is_match("ab", ".*") is True
    assert is_match("aaaaaaaaaaaaab", "a*a*a*a*a*a*a*a*a*a*b") is True
    assert is_match("aaaaaaaaaaaaab", "a*a*a*a*a*a*a*a*a*a*c") is False
