# Python Scripts

These repository contains some helper scripts I've written for day to day use. This was part of dotfiles repo before, now it's a different repo, cause why not?

Most stuff can be done with bash scripts, but it was way to difficult for me to run, and also my love for python.

Most files here are aliased conviniently in the [`aliasrc`](https://github.com/toxdes/dotfiles/blob/master/config_files/ALIASRC) of the dotfiles repo, to make them actually usable.

This repo also contains some `bash` files, cause they're super simple _and_ useful.

# Content

### 1. `youtube.py`

Helper script on top of `youtube-dl` to make downloading way easier.
Requires `xclipboard`.

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
```

### 2. `cc.py`

For compiling `C` and `C++` files, this was created when I was unaware of makefiles, but it's handy while testing `C` or `C++` code snippets.
Also included `prep` subcommand that takes / asks for a directory name, and optionally takes `-f` argument. 

`prep` command does the following: 
1. Ask for `dir_name` if not provided in args.
2. Create a new dir named `dir_name`.
3. If `-f` was provided then create 6 empty files in the newly created directory, namely `A.cpp, B.cpp, ..., F.cpp`, otherwise skip this step.
4. Copy `bits/stdc++.h` from the user's machine, to the newly created directory as `bits/stdc++.h`. This is useful, because it used to take 7ish seconds to compile each C++ file since my laptop is slow. Now, we precompile this header, so that each individual C++ file uses this header compiles in 1-2ish seconds. Huge time saved!
5. Compile the locally copied `bits/stdc++.h` header.
6. Done!

Nowadays, I use it a lot (especially the `prep` subcommand).

**Note** - This one's aliased conveniently in [`aliasrc`](https://github.com/toxdes/dotfiles/blob/master/config_files/ALIASRC). 

##### Examples

```shell
$ c test_pointers.c # Compile and run C file 
$ cpp wow.cpp # Compile and run C++ file
$ prep abc175 # do steps menotioned above.
```

### 3. `days.py`

For counting timespan, given the start-date. Handy to use when I have to find quickly time elapsed since some date, e.g. birthday.

##### Examples

```shell
$ days #gives time elapsed since predefined date
$ days <anything> # asks for a date, gives age
```

### 4. `attempts.py`

Created this when I was preparing for GATE. After each mock test, running this script would ask me details about the attempted, correct questions etc, what went wrong, and how would I improve etc. and save it as a text file.

`read` argument would list all such entries, which could be opened in the terminal right away.

##### Examples

```shell
$ attempts read # lists all attempts
$ attempts # create a new attempt, interactive
```

### 5. `nconvert.py`

For converting numbers to and from different number systems. This script was handy for GATE preparation as well, to check if my conversions are correct.

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

### 6. `googler.py`

This was created when I was unaware of DuckDuckGo's Bangs. Functionality is same, most used sites by me are included. Wanted to use terminal binary `googler`, but I guess it turned out to be inconvinient, so now links are opened in browser instead.

I don't use it anymore because of DuckDuckGo, so no examples for this.

### 7. `imports.py`

This is just because I wanted to avoid writing `import math`, everytime I wanted to use python as a calculator.

##### Examples

```shell
$ pc # imports mostly used modules
>>> log(10,2) # and starts this interactive shell
3.3219280948873626
>>>
```
