#!/usr/bin/python3

# this is just for using shell as a handy calculator
# it's aliased as pc, with command: python3 -i imports.py
from math import *
import os
import sys
import shlex
import subprocess

# easier to type factorial functionl
f = factorial

# combinations
def C(n,r):
    return f(n)/(f(r)*f(n-r))

# permutations
def P(n,r):
    return f(n)/(f(n-r))

# fuel cost 
def fuel(dist, mileage = 40, cost_per_l =109):
    return (dist*1.0 / mileage)*cost_per_l
