#!/usr/bin/env python3
import subprocess
import sys,os

USAGE = f"""
USAGE
    chop <input.mp3> <segments.txt> <output_dir>

DESCRIPTION
    Splits  input.mp3 file to smaller .mp3 files according to
    timestamps defined in 'segments.txt', and saves each file
    to the specified 'output_dir', 'output_dir' is created if
    it does not exist.

EXAMPLE

Sample segments.txt content -
00:05 INTRO
03:49 First Part
07:34 Second Part

would create split the input.mp3 into
INTRO.mp3 -> 00:05 - 03:48
First Part.mp3 -> 03:49 - 07:34
Second Part.mp3 -> 07:34 - 09:32 (Assuming 09:32 is the duration of input.mp3)
"""

def panic():
    print(USAGE)
    exit(1)
    
if(len(sys.argv) != 4):
    panic()

input_file = sys.argv[1]
segments_file = sys.argv[2]
dir_name = sys.argv[3]


# Parse the segments
with open(segments_file, "r") as f:
    lines = [line.strip() for line in f if line.strip()]

timestamps = []
titles = []

subprocess.run(['mkdir', '-p', dir_name])

for line in lines:
    time, title = line.split(" ", 1)
    timestamps.append(time)
    titles.append(title.strip().replace(" ", "_"))

# CHATGPT GENERATED -
# Process each segment with logging
for i in range(len(timestamps)):
    start = timestamps[i]
    end = timestamps[i + 1] if i + 1 < len(timestamps) else None
    title = titles[i]
    output_file = f"{dir_name}/{title}.mp3"

    print(f"[{i+1}/{len(timestamps)}] Exporting: {title} ({start} to {end or 'end'})")

    cmd = ["ffmpeg", "-y", "-i", input_file, "-ss", start]
    if end:
        cmd += ["-to", end]
    cmd += ["-vn", "-acodec", "libmp3lame", output_file]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error processing {title}: {result.stderr}")
    else:
        print(f"Saved as: {output_file}")

