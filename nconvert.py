#!/usr/bin/python3
import sys
# number systems
args = sys.argv
nums = []
def print_all(nums, base):
    for n in nums:
        print(f'Decimal:{n}')
        print(f'Binary:{bin(n)}')
        print(f'Octal:{oct(n)}')
        print(f'Hex:{hex(n)}')

if len(args) <=1:
    base = int(input("Base : "))
    n = int(input("Number : "), base)
    nums.append(n)
elif len(args) == 2:
    base = 10
    n = int(args[1])
    nums.append(int(n, base))
else:
    base = int(args[1])
    nums = [int(i,base) for i in args[2:]]

print_all(nums, base)
