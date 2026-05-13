#!/usr/bin/env python3
import subprocess
import sys

INTERFACE = "wlp3s0"

def run(cmd):
    print(f"[+] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()

def get_networks():
    output = run(["sudo", "wpa_cli", "-i", INTERFACE, "list_networks"])
    lines = output.splitlines()

    if len(lines) < 2:
        return []

    networks = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= 2:
            net_id = parts[0].strip()
            ssid = parts[1].strip()
            flags = parts[3].strip() if len(parts) >= 4 else ""
            if ssid:
                networks.append({
                    "id": net_id,
                    "ssid": ssid,
                    "flags": flags
                })
    return networks

def print_networks(networks):
    print("Available Wi-Fi networks:\n")
    for idx, net in enumerate(networks, start=1):
        extra = f" {net['flags']}" if net["flags"] else ""
        print(f"{idx}. {net['ssid']}{extra}")
    print()

def choose_network(networks):
    while True:
        choice = input("Enter number to switch Wi-Fi (or q to quit): ").strip()

        if choice.lower() in {"q", "quit", "exit"}:
            print("Aborted.")
            sys.exit(0)

        if not choice.isdigit():
            print("Please enter a valid number.")
            continue

        num = int(choice)
        if 1 <= num <= len(networks):
            return networks[num - 1]

        print(f"Please enter a number between 1 and {len(networks)}.")

def switch_network(net):
    print(f"\nSwitching to: {net['ssid']}")
    run(["sudo", "wpa_cli", "-i", INTERFACE, "select_network", net["id"]])
    run(["sudo", "wpa_cli", "-i", INTERFACE, "reassociate"])

    status = run(["sudo", "wpa_cli", "-i", INTERFACE, "status"])
    print("\nCurrent status:\n")
    print(status)

def main():
    networks = get_networks()

    if not networks:
        print("No saved Wi-Fi networks found in wpa_supplicant.")
        sys.exit(1)

    print_networks(networks)
    selected = choose_network(networks)
    switch_network(selected)

if __name__ == "__main__":
    main()
        
