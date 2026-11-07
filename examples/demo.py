"""A tour of mathguard: typical mistakes and how they are caught.

Run with:  python examples/demo.py
"""

import mathguard as mg

print("1) A sign error in the middle of a derivation\n")
print(mg.check_chain([
    "(x+1)^2 - (x-1)^2",
    "x^2 + 2x + 1 - x^2 - 2x + 1",   # forgot to distribute the minus sign
    "2",
]))

print("\n2) An identity that only holds for positive numbers\n")
print(mg.check_equal("log(x y)", "log(x) + log(y)"))
print(mg.check_equal("log(x y)", "log(x) + log(y)", {"x": "positive", "y": "positive"}))

print("\n3) Forgotten chain rule\n")
print(mg.check_derivative("sin(omega t)", "cos(omega t)", variable="t"))

print("\n4) Incomplete solution set\n")
print(mg.check_solutions("x^3 = x", "x", ["0", "1"]))

print("\n5) Units don't match\n")
print(mg.check_dimensions({"F": "N", "m": "kg", "v": "m/s", "r": "m"},
                          equation="F = m v / r"))
print(mg.check_dimensions({"F": "N", "m": "kg", "v": "m/s", "r": "m"},
                          equation="F = m v^2 / r"))

print("\n6) Classical limit of relativistic kinetic energy\n")
print(mg.check_limit("(1/sqrt(1 - v^2/c^2) - 1) m c^2", "c", "oo", "1/2 m v^2",
                     {"c": "positive", "v": "positive"}))
