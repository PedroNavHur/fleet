def pick(a, b, c):
    if a > 1 and b and c:
        for x in [1, 2]:
            if x or b:
                return x
    elif a < 0:
        return 2 if a else 3
    else:
        try:
            a += 1
        except Exception:
            return 0
    return 1
def a1(a, b, c):
    if a > 1 and b and c:
        return 1
    return 0
def a2(a):
    if a:
        return 1
    elif a < 0:
        return 2
    else:
        return 3
def a5(b):
    if b:
        for x in [1]:
            if x or b:
                return x
    return 0
def a8(a, b):
    return a > 1 and b or not b and a < 3
def a9(a):
    f = lambda x: 1 if x else 0
    return f(a)
def a13(n):
    return 1 if n <= 1 else n * a13(n - 1)
def a14(a):
    while a:
        a -= 1
    return a
class K:
    def m(self, n):
        return self.m(n - 1) if n else 0
