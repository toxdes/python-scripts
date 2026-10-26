#!/usr/bin/env python3
"""Show windows from every sway workspace in rofi and focus the selection."""

import json
import subprocess
import sys


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, check=True, **kwargs)


def window_entries(tree):
    entries = []

    def visit(node, workspace=""):
        if node.get("type") == "workspace":
            workspace = node.get("name", workspace)

        children = node.get("nodes", []) + node.get("floating_nodes", [])
        if not children and (node.get("app_id") or node.get("window") is not None):
            title = node.get("name") or "(untitled)"
            app = node.get("app_id") or node.get("window_properties", {}).get("class") or "window"
            label = f"[{workspace}] {app} | {title}"
            if node.get("urgent"):
                label = f"[URGENT]  {label}"
            entries.append((node["id"], label))
            return

        for child in children:
            visit(child, workspace)

    visit(tree)
    return entries


def main():
    try:
        tree = json.loads(run(["swaymsg", "-t", "get_tree"]).stdout)
        entries = window_entries(tree)
        if not entries:
            return

        # Rofi returns the selected input row number, avoiding ambiguity when
        # multiple windows have the same title.
        selected = subprocess.run(
            ["rofi", "-dmenu", "-i", "-p", "Windows", "-format", "i"],
            input="\n".join(label for _, label in entries),
            capture_output=True,
            text=True,
        )
        if selected.returncode != 0 or not selected.stdout.strip():
            return

        index = int(selected.stdout.strip())
        if 0 <= index < len(entries):
            run(["swaymsg", f"[con_id={entries[index][0]}]", "focus"])
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as error:
        print(f"window_picker.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
