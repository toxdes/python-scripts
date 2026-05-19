#!/usr/bin/python3
import subprocess
import os
import json
from datetime import datetime

SERVICES = ["counter-server", "stats-server"]
METRICS_DIR = "./metrics"

def human_bytes(b):
    if b is None or b == "" or b == "[not set]" or b == 18446744073709551615:
        b = 0
    b = int(b)
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(b)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    if i == 0:
        return f"{val:.0f} {units[i]}"
    return f"{val:.2f} {units[i]}"

def uptime_from_timestamp(ts):
    if not ts or ts == "n/a":
        return "n/a"
    try:
        ts_no_tz = " ".join(ts.split(" ")[:-1])
        start_ts = datetime.strptime(ts_no_tz, "%a %Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return str(ts)
    now = datetime.now()
    diff = int((now - start_ts).total_seconds())
    if diff < 0:
        diff = 0
    days = diff // 86400
    hours = (diff % 86400) // 3600
    mins = (diff % 3600) // 60
    secs = diff % 60
    if days > 0:
        return f"{days}d {hours:02d}h {mins:02d}m"
    elif hours > 0:
        return f"{hours}h {mins:02d}m {secs:02d}s"
    elif mins > 0:
        return f"{mins}m {secs:02d}s"
    return f"{secs}s"

def systemctl_show(service, prop):
    res = subprocess.run(
        ["systemctl", "show", service, "-p", prop, "--value"],
        capture_output=True, text=True
    )
    return res.stdout.strip()

def sanitize(val):
    if not val or val == "[not set]":
        return 0
    return val

def main():
    os.makedirs(METRICS_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_file = os.path.join(METRICS_DIR, f"{timestamp}.json")

    host = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
    collected_at = datetime.now().astimezone().isoformat()

    divider = "-" * 80

    print()
    print(divider)
    print(f"{'SERVICE':<16} {'STATUS':<10} {'MEMORY':<10} {'TASKS':<8} {'RESTARTS':<10} {'UPTIME':<24}")
    print(divider)

    services = []
    total_mem = 0

    for s in SERVICES:
        status = systemctl_show(s, "SubState")
        if not status:
            status = "unknown"

        mem_raw = systemctl_show(s, "MemoryCurrent")
        mem = sanitize(mem_raw)
        mem = int(mem) if mem != 0 else 0
        mem_h = human_bytes(mem)
        total_mem += mem

        tasks_raw = systemctl_show(s, "TasksCurrent")
        tasks = sanitize(tasks_raw)
        tasks = int(tasks) if tasks != 0 else 0

        restarts_raw = systemctl_show(s, "NRestarts")
        restarts = restarts_raw if restarts_raw else 0
        restarts = int(restarts)

        active_ts = systemctl_show(s, "ActiveEnterTimestamp")
        if not active_ts:
            active_ts = "n/a"
        uptime_human = uptime_from_timestamp(active_ts)

        try:
            ts_no_tz = " ".join(active_ts.split(" ")[:-1])
            start_ts = datetime.strptime(ts_no_tz, "%a %Y-%m-%d %H:%M:%S")
            uptime_seconds = int((datetime.now() - start_ts).total_seconds())
        except (ValueError, TypeError):
            uptime_seconds = 0
        if uptime_seconds < 0:
            uptime_seconds = 0

        print(f"{s:<16} {status:<10} {mem_h:<10} {tasks:<8} {restarts:<10} {uptime_human:<24}")

        services.append({
            "service": s,
            "status": status,
            "memory_bytes": mem,
            "memory_human": mem_h,
            "tasks_current": tasks,
            "n_restarts": restarts,
            "active_enter_timestamp": active_ts,
            "uptime_seconds": uptime_seconds,
            "uptime_human": uptime_human,
        })

    summary = {
        "total_memory_bytes": total_mem,
        "total_memory_human": human_bytes(total_mem),
    }

    result = {
        "host": host,
        "collected_at": collected_at,
        "services": services,
        "summary": summary,
    }

    with open(json_file, "w") as f:
        json.dump(result, f, indent=2)

    print(divider)
    print(f"{'TOTAL MEMORY':<16} {human_bytes(total_mem):<10}")
    print(divider)
    print(f"Saved metrics to {json_file}\n")

if __name__ == "__main__":
    main()
