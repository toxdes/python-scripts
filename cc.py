#!/usr/bin/python3
# I'm an idiot btw, what I wanted to achieve with this script
# `make` is the right tool for it.
# I should just spend some time with bash, this is getting embarrasing.

import subprocess
import shlex
import sys
import os

options = {}

c_flags = "-std=c11 -g -Weverything -O0"
cpp_flags = "-std=c++17 -g -O0"
options['c'] = f'clang {c_flags}'
options['cpp'] = f'clang++ {cpp_flags}'

args = sys.argv

lang = args[1]

# prep means create cpp files for each problem, in file too
if(lang == 'prep'):
    dirname = input("Directory Name: ")
    path = os.path.abspath(os.curdir)
    cmd = []
    cmd.append(f"mkdir -p {path}/{dirname}")
    for a in ['A', 'B', 'C', 'D', 'E', 'F']:
        cmd.append(f'touch  {path}/{dirname}/{a}.cpp')
    cmd.append(f'touch  {path}/{dirname}/in')
    for each in cmd:
        print(each)
        subprocess.run(shlex.split(each))
    print("created directories and files, you should be okay")
    exit()

output_file = args[2].split('.')[:-1]
output_file = ".".join(output_file)
cmd = f'{options[lang]} {os.path.abspath(os.curdir)}/{args[2]} -o {output_file}'

# print(cmd)
print('Compiling...', end="")
status = subprocess.run(shlex.split(cmd))

if status.returncode != 0:
    print("Something unusual happened, Abort.")
    exit()

print('Done!')

print("\n-------- OUTPUT --------\n")

cmd = f'./{output_file}'
subprocess.run(shlex.split(cmd))
print()
