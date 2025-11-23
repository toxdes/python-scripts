#!/usr/bin/python3

# this is just for using shell as a handy calculator
# it's aliased as pc, with command: python3 -i imports.py
import os
import shlex
import subprocess
import sys
from math import *

# easier to type factorial functionl
f = factorial


# combinations
def C(n, r):
    return f(n) / (f(r) * f(n - r))


# permutations
def P(n, r):
    return f(n) / (f(n - r))


# fuel cost
def fuel(dist, mileage=40, cost_per_l=109):
    return (dist * 1.0 / mileage) * cost_per_l


def usage():
    print(
        "extras:\n\tf(x) -> factorial\n\tC(n,r) -> nCr\n\tP(n,r) -> nPr\n\tfuel(dist,mileage,cost_per_l) -> how much would it cost to travel 'dist' km\nNote: enter `usage()` to print this message again."
    )


usage()
