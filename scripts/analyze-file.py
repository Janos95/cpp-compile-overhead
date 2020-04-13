#!/usr/bin/env python3

import math
import re
import argparse
import os
import sys
import subprocess
import time
import json

parser = argparse.ArgumentParser(description="C++ compile-health analyzer")
parser.add_argument("file", metavar="F", type=str,
                    help="C++ source or header file to analyze")
parser.add_argument("-c", "--compiler", required=True,
                    type=str, help="compiler to use")
parser.add_argument("-d", "--dir", required=True, type=str,
                    help="temporary directory to use (e.g. /tmp)")
parser.add_argument(
    "args", type=str, help="additional compile args (use -- to prevent clashes with other args)", nargs="*")
parser.add_argument("-v", "--verbose", help="increase output verbosity",
                    action="store_true")

args = parser.parse_args()


def debug_print(s):
    if args.verbose:
        print(s)


def debug_print_exec(a):
    if args.verbose:
        print("executing {}".format(a))

# ============================================================
# Parse args


compiler = args.compiler
debug_print("compiler: " + compiler)
assert os.path.isabs(
    compiler), "compiler path must be absolute! (to prevent lookup dominating time measurement)"
assert os.path.exists(compiler), "cannot find compiler"

file = args.file
debug_print("file: " + file)
is_source = os.path.splitext(file)[-1].startswith(".c")
is_header = os.path.splitext(file)[-1].startswith(".h")
is_system = os.path.splitext(file)[-1] == ""
debug_print("is_source: " + str(is_source))
debug_print("is_header: " + str(is_header))
debug_print("is_system: " + str(is_system))
assert is_source or is_header or is_system, "unknown extension"

tmp_dir = args.dir
debug_print("tmp dir: " + tmp_dir)
assert os.path.exists(tmp_dir), "tmp dir does not exist"
tmp_dir = os.path.abspath(tmp_dir)

cargs = args.args
debug_print("{} additional arguments".format(len(cargs)))
for a in cargs:
    debug_print("  {}".format(a))


# ============================================================
# Setup

file_main = os.path.join(tmp_dir, "main.cc")
baseline_main = os.path.join(tmp_dir, "baseline.cc")
output_main = os.path.join(tmp_dir, "main.o")
result = {}
preproc_args = [compiler] + cargs + ["-I.", "-E", file_main, "-o", output_main]
compile_args = [compiler] + cargs + ["-I.", "-c", file_main, "-o", output_main]
preproc_baseline_args = [compiler] + cargs + \
    ["-I.", "-E", baseline_main, "-o", output_main]
compile_baseline_args = [compiler] + cargs + \
    ["-I.", "-c", baseline_main, "-o", output_main]


# ============================================================
# Create temporary files to compile

with open(file_main, "w") as f:
    f.writelines([
        "#include <" + file + ">\n",
        "int main() { return 0; }\n"
    ])

with open(baseline_main, "w") as f:
    f.writelines([
        "int main() { return 0; }\n"
    ])


# ============================================================
# Check stats

# -E is preprocessor only (and strips comments)
debug_print_exec(preproc_args)
subprocess.run(preproc_args, check=True)
with open(output_main) as f:
    line_cnt_raw = 0
    line_cnt = 0
    prog = re.compile(r'[a-zA-Z0-9_]')
    for l in f.readlines():
        line_cnt_raw += 1

        if prog.search(l) is not None:
            line_cnt += 1
    result["line_count_raw"] = line_cnt_raw - 2  # int main() + #include
    result["line_count"] = line_cnt - 1  # int main()

# -c compiles to object file
debug_print_exec(compile_args)
subprocess.run(compile_args, check=True)
result["object_size"] = os.path.getsize(output_main)

# check symbols
prog = re.compile(r'^[0-9a-zA-Z]* +(\w) (.+)$')
undef_sym_cnt = 0
undef_sym_size = 0
data_sym_cnt = 0
data_sym_size = 0
code_sym_cnt = 0
code_sym_size = 0
debug_print_exec(["nm", output_main])
for l in subprocess.check_output(["nm", output_main]).decode("utf-8").splitlines():
    m = prog.match(l)
    assert m is not None, "could not parse line " + l
    st = m.group(1)
    sn = m.group(2)

    if st in ['u', 'U']:
        undef_sym_cnt += 1
        undef_sym_size += len(sn)
    elif st in ['b', 'B', 'r', 'R', 'd', 'D']:
        data_sym_cnt += 1
        data_sym_size += len(sn)
    elif st in ['t', 'T']:
        code_sym_cnt += 1
        code_sym_size += len(sn)
    else:
        assert False, "unknown symbol type " + st

result["undefined_symbol_count"] = undef_sym_cnt
result["undefined_symbol_size"] = undef_sym_size
result["data_symbol_count"] = data_sym_cnt
result["data_symbol_size"] = data_sym_size
result["code_symbol_count"] = code_sym_cnt
result["code_symbol_size"] = code_sym_size

# baseline object size
debug_print_exec(compile_baseline_args)
subprocess.run(compile_baseline_args, check=True)
result["object_size_base"] = os.path.getsize(output_main)


# ============================================================
# Check parse and compile times

def measure_time(sargs):
    ts = []
    while True:
        if len(ts) > 20:
            break
        if len(ts) >= 8:
            ts.sort()
            if ts[3] / ts[0] < 1.01:  # cheapest 4 deviate less than 1%
                break

        t0 = time.perf_counter()
        subprocess.call(sargs)
        t1 = time.perf_counter()
        ts.append(t1 - t0)
    ts.sort()
    return ts[0]


result["preprocessing_time"] = measure_time(preproc_args)
result["compile_time"] = measure_time(compile_args)
result["preprocessing_time_base"] = measure_time(preproc_baseline_args)
result["compile_time_base"] = measure_time(compile_baseline_args)


# ============================================================
# Finalize

debug_print("")
debug_print("results:")

print(json.dumps(result, indent=4))
