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


def format_with_groups(s, group_size=4):
    """Format string in groups of 4 with spaces."""
    parts = [s[i : i + group_size] for i in range(0, len(s), group_size)]
    return " ".join(parts)


def num(n):
    """Convert number to all common bases (decimal, binary, octal, hex) with nice formatting."""
    print(f"Decimal: {n}")

    # Get all representations
    binary = bin(n)[2:]  # remove '0b' prefix
    octal = oct(n)[2:]  # remove '0o' prefix
    hexval = hex(n)[2:]  # remove '0x' prefix

    # Find max length and pad all to that length
    max_len = max(len(binary), len(octal), len(hexval))
    binary = binary.zfill(max_len)
    octal = octal.zfill(max_len)
    hexval = hexval.zfill(max_len)

    # Format with groups of 4
    formatted_binary = format_with_groups(binary)
    print(f"-> 0b {formatted_binary}")

    formatted_octal = format_with_groups(octal)
    print(f"-> 0o {formatted_octal}")

    formatted_hex = format_with_groups(hexval)
    print(f"-> 0x {formatted_hex}")


def usage():
    print(
        "extras:\n\tf(x) -> factorial\n\tC(n,r) -> nCr\n\tP(n,r) -> nPr\n\tfuel(dist,mileage,cost_per_l) -> how much would it cost to travel 'dist' km\n\tnum(n) -> convert number to decimal, binary, octal, hex\nNote: enter `usage()` to print this message again."
    )


usage()
