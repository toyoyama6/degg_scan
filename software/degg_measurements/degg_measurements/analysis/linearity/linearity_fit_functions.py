import numpy as np


# fitting function
def linearity_current_curve_func(x, p0, p1, p2):
    return (1./x + (1./p0) * np.log1p((x/p1)**3) /
            np.log1p(x/p2)) ** -1


def linearity_current_curve_func2(x, p0, p1, p2):
    return (1./x + (1./p0) * np.log1p((x/p1)**3) /
            np.log1p((x/p2)**0.5)) ** -1


# add p3 compression factor
def linearity_current_curve_func3(x, p0, p1, p2, p3):
    return (1./(x*p3) + (1./p0) * np.log1p((x*p3/p1)**3) /
            np.log1p(x*p3/p2))**-1


def linearity_Tilo_func(x, Is, A, B):
    # Tilo Waldemeier function x: I_ide
    lna = np.log1p(A / x)
    return x * (lna / (lna + A /Is * np.exp(-B / x)))

