import subprocess
import argparse
import shlex
import os
import sys
import glob


class colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


WORKDIR = os.path.abspath(os.curdir)
FILENAME = "a.cpp"
DEVNULL = open(os.devnull, 'w')
CUSTOM = False

if("custom" in sys.argv):
    CUSTOM = True


# TODO: check if the source is changed and compile only if it is changed
print(f" ⏳ {colors.WARNING}Compiling...{colors.END}", end="")
subprocess.run(shlex.split(
    f"g++ -std=c++17 {WORKDIR}/{FILENAME} -o {WORKDIR}/samples/a"))
print(f" ✅ {colors.GREEN}Done{colors.END}" + ' '*10)
sys.stdout.flush()

if(CUSTOM):
    print(f"{colors.BLUE} 🔵 Running Custom Invocation {colors.END}")
    try:
        subprocess.run(shlex.split(f'{WORKDIR}/samples/a'))
    except:
        os.mkdir(f'{WORKDIR}/samples')
        subprocess.run(shlex.split(f'{WORKDIR}/samples/a'))
    sys.stdout.flush()
    exit(0)

listing = glob.glob(f'{WORKDIR}/samples/in*')
for i, each in enumerate(listing):
    print(
        f' ⏳ {colors.WARNING}{colors.BOLD}Running Testcase {i+1}...{colors.END}', end="")
    sys.stdout.flush()
    in_f = open(f'{WORKDIR}/samples/in{i+1}', 'r')
    out_f = open(f'{WORKDIR}/samples/res{i+1}', 'w+')
    ans_f = open(f'{WORKDIR}/samples/out{i+1}', 'r')
    err_f = open(f'{WORKDIR}/samples/err{i+1}', 'w+')
    try:
        p = subprocess.run(shlex.split(
            f'{WORKDIR}/samples/a'), stdin=in_f, stdout=out_f, stderr=err_f, timeout=2)
        exit_code = p.returncode
        in_f.close()
        out_f.close()
        ans_f.close()
        err_f.close()
        okay = subprocess.run(shlex.split(
            f"diff -q {WORKDIR}/samples/res{i+1} {WORKDIR}/samples/out{i+1}"), stdout=DEVNULL, stderr=DEVNULL).returncode
        if(okay == 0):
            print(f" ✅ {colors.BOLD}{colors.GREEN}Passed{colors.END}")
            continue
        print(f" ❌ {colors.BOLD}{colors.FAIL}Wrong Answer")
        print(" Process exited with code", exit_code)
        print(f'{colors.END}')
        out_f = open(f'{WORKDIR}/samples/res{i+1}', 'r')
        ans_f = open(f'{WORKDIR}/samples/out{i+1}', 'r')
        err_f = open(f'{WORKDIR}/samples/err{i+1}', 'r')

        print('--- Your Output ---')

        for line in out_f.readlines():
            print(line, end="")
        print()
        print('--- Expected Answer ---')
        for line in ans_f.readlines():
            print(line, end="")
        print()
        print('--- STDERR ---')
        for line in err_f.readlines():
            print(line, end="")
        print('---------')
        out_f.close()
        ans_f.close()
        err_f.close()
    except:
        print(f" ❌ {colors.BOLD}{colors.FAIL} Time Limit Exceeded {colors.END}")
