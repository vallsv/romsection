import itertools
import numpy


def prime_factors(n: int):
    if n == 0:
        return []
    spf = [0 for i in range(n+1)]
    spf[1] = 1
    for i in range(2, n+1):
        spf[i] = i
    for i in range(4, n+1, 2):
        spf[i] = 2
 
    for i in range(3, int(n**0.5)+1):
        if spf[i] == i:
            for j in range(i*i, n+1, i):
                if spf[j] == j:
                    spf[j] = i

    result = []
    while n != 1:
        result.append(spf[n])
        n = n // spf[n]

    return result


def guessed_shapes(size: int) -> list[tuple[int, int]]:
    result = []
    factors = prime_factors(size)
    for filter in itertools.product([False, True], repeat=len(factors)):
        width = int(numpy.prod([fa for fa, fi in zip(factors, filter) if fi]))
        result.append((width, size // width))
    return sorted(list(set(result)))
