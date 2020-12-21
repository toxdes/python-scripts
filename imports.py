#!/usr/bin/python3

# this is just for using shell as a handy calculator
# it's aliased as pc, with command: python3 -i imports.py
from math import *
import os
import sys
import shlex
import subprocess

# combinations
def C(n,r):
    return factorial(n)/(factorial(r)*factorial(n-r))

# permutations
def P(n,r):
    return factorial(n)/(factorial(n-r))
