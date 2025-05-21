def list_factors(n):
    """
    Returns a list of all factors of the given integer n.

    Parameters:
    n (int): The integer to find factors for.

    Returns:
    list: A list of factors of n.
    """
    if n == 0:
        return []  # Zero has an infinite number of factors
    factors = []
    n = abs(n)  # Consider absolute value for factors
    for i in range(1, int(n**0.5) + 1):
        if n % i == 0:
            factors.append(int(i))  # Add the divisor
            if i != n // i:
                factors.append(int(n // i))  # Add the corresponding pair divisor
    factors.sort()
    return factors
