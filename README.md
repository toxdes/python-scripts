# Python Scripts

This repository contains some helper scripts I've written for day-to-day use. It was part of the [dotfiles repo](https://github.com/toxdes/dotfiles) earlier, but is now a separate repository for easier maintenance.

### Notes:
1. Most of the things here can usually be achieved by using `bash` or `<your favourite shell>`, but `python` is easier.

2. Most files here are aliased conveniently in the [`aliasrc`](https://github.com/toxdes/dotfiles/blob/master/config-files/ALIASRC) of the dotfiles repo, to make them actually usable.

# Content

### 1. `youtube.py`

**Depends On**: `xclipboard` and `youtube-dl` (`youtube-dlp`).

This is a helper script on top of `youtube-dl` to make downloading way easier. This script can be installed by running `curl -fsSL sh.txds.me/yt | bash`, it installs both `youtube-dlp` and this wrapper script as well.

```shell
usage: youtube.py [-h] [-c] [-p] [-q {240p,360p,480p,720p,1080p,1440p}] [-a] [-o OUTPUT_DIR] [-r] [-i] [-e] [-t]

Helper Script for youtube-dl.

optional arguments:
  -h, --help            show this help message and exit
  -c                    Get video link from clipboard.
  -p                    Treat the link as if it is a playlist.
  -q {240p,360p,480p,720p,1080p,1440p}
                        Default is 360p
  -a                    Download best quality audio only.
  -o OUTPUT_DIR         Default is current directory.
  -r                    Do not download, just output the generated command only.
  -i                    Print list of available formats to download.
  -e                    Use aria2c as the external downloader
  -t                    Custom script for twitch
```

##### Examples

```shell
$ yt -cq 720p # video
$ yt -cap # mp3 songs playlist
$ yt -cpq 480p # downloading lectures playlist
$ yt -rcpq 1080p # debug, check if the command is okay
$ yt -tcq 360p # download twitch vod
```


### 2. `display.py`

**Depends On**: `xrandr` (X11) or `wlr-randr` (Wayland).

Manages display configurations for multi-monitor setups. Supports switching between `laptop_only`, `external_only`, `external_mirrors_laptop`, and `external_extends_laptop`. 

You need to first populate `Config` class to match your setup before use.

```shell
Usage: ./display.py <laptop_only | external_only | external_mirrors_laptop | external_extends_laptop>
```

##### Examples

```shell
$ ./display.py laptop_only
$ ./display.py external_only
$ ./display.py external_mirrors_laptop
$ ./display.py external_extends_laptop
```

### 3. `cc.py` and `cparser`

This script is useful for compiling `C` and `C++` files, this was created when I was unaware of makefiles, but it's handy while testing `C` or `C++` code snippets.
Also included `prep` subcommand that takes / asks for a directory name, and optionally takes `-f` argument.

_All scripts are aliased conveniently in [`aliasrc`](https://github.com/toxdes/dotfiles/blob/master/config-files/ALIASRC)._

`prep` command does the following:

1. Ask for `dir_name` if not provided in args.
2. Create a new dir named `dir_name`.
3. If `-f` was provided then create 6 empty files in the newly created directory, namely `A.cpp, B.cpp, ..., F.cpp`, otherwise skip this step.
4. Copy `bits/stdc++.h` from the user's machine to the newly created directory. This is useful because it used to take ~7 seconds to compile each C++ file on a slow laptop. By precompiling this header locally, each individual C++ file now compiles in ~1-2 seconds—huge time savings!
5. Compile the locally copied `bits/stdc++.h` header.
6. Done!


###### Notes for cparser

`server.py` listens to POST requests to a specified port, the competitive
companion browser extension posts parsed problems to this endpoint,
and creates a `samples` directory, for each testcase.

`run.py` compiles and runs the program against the parsed sample test
cases.

`run.py custom` compiles, and runs against user input.

`server.py` is used as a daemon process, in the background so it's
aliased as `cphd`.

`run.py` is used as a script, so it's aliased as `cpr`.

##### Examples

```shell
$ c test_pointers.c # compiles and runs the C file
$ cpp wow.cpp # compiles and runs the C++ file
$ prep abc175 # does the steps mentioned above
```


### 4. `days.py`

Counts the time elapsed since a given start date. Handy for quickly finding how much time has passed since some date, e.g., a birthday.

##### Examples

```shell
$ days #gives time elapsed since predefined date
$ days <anything> # asks for a date, gives age
```

### 5. `nconvert.py`

Converts numbers to and from different number systems. This script was also handy for GATE preparation for quickly revalidating conversions during calculations.

##### Examples

```shell
$ nums # interactive
Base : 16 # enter base
Number : ffc # number
Decimal:4092 # results
Binary:0b111111111100
Octal:0o7774
Hex:0xffc
```

### 6. `imports.py`

Created to avoid repeatedly writing `import math` every time I want to use Python as a calculator.
It also includes additional functions from combinatorics. 

##### Examples

```shell
$ pc # imports mostly used modules
>>> log(10,2) # and starts this interactive shell
3.3219280948873626
>>>
# or 
$ pc
>>> C(12,5) # binomial coeff.
```

### 7. `chop.py`
##### USAGE
**Depends on:**  `ffmpeg`.
```shell
$ chop <input.mp3> <segments.txt> <output_dir>
```
Splits `input.mp3` file to smaller `.mp3` files according to timestamps defined in `segments.txt`, and saves each file to the specified `output_dir`, `output_dir` is created if it does not exist. 


##### Sample segments.txt
```
00:05 INTRO
03:49 First Part
07:34 Second Part
```
will split the `input.mp3` into
```
INTRO.mp3 -> 00:05 - 03:48
First Part.mp3 -> 03:49 - 07:34
Second Part.mp3 -> 07:34 - 09:32
```

Assuming 09:32 is the duration of `input.mp3`
