#!/usr/bin/python3
import sys
import json
import os

def main():
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <metrics.json>")

    json_file = sys.argv[1]
    if not os.path.isfile(json_file):
        sys.exit(f"File not found: {json_file}")

    with open(json_file, "r") as f:
        data = json.load(f)

    divider = "-" * 80

    print(divider)
    print(f"{'SERVICE':<16} {'STATUS':<10} {'MEMORY':<10} {'TASKS':<8} {'RESTARTS':<10} {'UPTIME':<24}")
    print(divider)

    for svc in data.get("services", []):
        print(f"{svc['service']:<16} {svc['status']:<10} {svc['memory_human']:<10} {svc['tasks_current']:<8} {svc['n_restarts']:<10} {svc['uptime_human']:<24}")

    print(divider)
    total_mem = data.get("summary", {}).get("total_memory_human", "0 B")
    print(f"{'TOTAL MEMORY':<16} {total_mem:<10}")
    print(divider)
    print(f"Loaded metrics from {json_file}\n")

if __name__ == "__main__":
    main()
