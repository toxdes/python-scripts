#!/usr/bin/python3
# I'm an idiot btw, what I wanted to achieve with this script
# `make` is the right tool for it.
# I should just spend some time with bash, this is getting embarrasing.

import subprocess
import shlex
import sys
import os

options = {}

c_flags = "-std=c11 -g -Wall"
cpp_flags = "-std=c++17"
options['c'] = f'gcc {c_flags}'
options['cpp'] = f'g++ {cpp_flags}'

args = sys.argv

lang = args[1]

# prep means create cpp files for each problem, in file too
# precompile the headers to save time during actual compilations
# because it's taking 7ish seconds to compile each time
# which is true pain.

if(lang == 'prep'):
    dirname = None
    if(len(args) > 1):
        dirname = args[2]
    else:
        dirname = input("Directory: ")
    path = os.path.abspath(os.curdir)
    create_files = False
    for e in args:
        if e == "-f":
            create_files = True
    cmd = []
    cmd.append(f"mkdir -p {path}/{dirname}")
    cmd.append(f"mkdir -p {path}/{dirname}/bits")
    if create_files:
        for a in ['A', 'B', 'C', 'D', 'E', 'F']:
            cmd.append(f'touch  {path}/{dirname}/{a}.cpp')
    cmd.append(f'touch  {path}/{dirname}/in')
    for each in cmd:
        print(each)
        subprocess.run(shlex.split(each))
    print("Created directory and default files...")
    # grab the path of actual bits/stdc++.h header file
    STD_CPP_HEADER_PATH = "/usr/include/x86_64-linux-gnu/c++/9/bits/stdc++.h"
    subprocess.run(shlex.split(
        f'cp {STD_CPP_HEADER_PATH} {path}/{dirname}/bits/'))
    print("Copied bits/stdc++.h")
    subprocess.run(shlex.split(
        f'g++ --std=c++17 {path}/{dirname}/bits/stdc++.h -o {path}/{dirname}/bits/stdc++.h.gch'))
    print("Compiled header. All good.")
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
