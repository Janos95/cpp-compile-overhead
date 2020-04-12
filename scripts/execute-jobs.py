#!/usr/bin/env python3

import os
import argparse
import subprocess
import platform
import json

parser = argparse.ArgumentParser(description="Execute jobs for C++ compile-health analyzer")
parser.add_argument("file", metavar="J", help="jobs file (e.g. jobs.json)")
parser.add_argument("result", metavar="R", help="result file (e.g. data.js)")
parser.add_argument("-c", "--cache", required=True, help="cache file")
parser.add_argument("-d", "--dir", required=True, type=str, help="temporary directory to use (e.g. /tmp)")
parser.add_argument("-v", "--verbose", help="increase output verbosity",
                    action="store_true")

args = parser.parse_args()

cache_file = args.cache
job_cache = {}


# ===============================================
# read jobs and cache

with open(args.file, "r") as f:
     jobs = json.load(f)
if os.path.exists(cache_file):
    with open(cache_file, "r") as f:
        job_cache = json.load(f)

print("executing {} jobs".format(len(jobs)))
print("found {} cached jobs in total".format(len(job_cache)))

analyzer_script = "scripts/analyze-file.py"
assert os.path.exists(analyzer_script), "must run in root dir of project"
analyzer_script = os.path.abspath(analyzer_script)

found_cached = 0

idx = 0

for j in jobs:
    id = []
    id.append(j["file"])
    id.append(j["compiler"])
    id += j["args"]
    id = ":".join(id)
    
    res = {}

    if id in job_cache:
        res = job_cache[id]
        found_cached += 1
    else:
        sargs = [analyzer_script, "-c", j["compiler"], "-d", args.dir, j["file"], "--"] + j["args"]
        if args.verbose:
            print("executing {}".format(sargs))
        res = subprocess.check_output(sargs).decode("utf-8")
        res = json.loads(res)
        job_cache[id] = res

        # write cache
        with open(cache_file, "w") as f:
            json.dump(job_cache, f, indent=4)

    j["id"] = idx
    j["argstr"] = " ".join(j["args"])
    for k in res:
        j[k] = res[k]
    idx += 1

print("was able to reuse {} results from cache".format(found_cached))

with open(args.result, "w") as f:
    f.write("var table_data = " + json.dumps(jobs, indent=4) + ";")
