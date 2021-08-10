#!/usr/bin/python3
# helper code for using youtube-dl
# not complete yet, need to add a output format option, save to directory option
# almost complete, just testing is remaining. Should be useful by now.
from argparse import ArgumentParser
from pprint import pprint
import shlex
import os
import subprocess

# constants
choices = ['240p', '360p', '480p', '720p', '1080p', '1440p']
current_dir = os.path.abspath(os.curdir)
DEFAULT_CHOICE = 1
output_format = 'mkv'

parser = ArgumentParser(description="Helper Script for youtube-dl.")
parser.add_argument('-c', dest="link_from_clipboard",
                    help="Get video link from clipboard.", action="store_true")
parser.add_argument('-p', dest="playlist",
                    help="Treat the link as if it is a playlist.", action="store_true")
parser.add_argument('-q', dest="quality",
                    help=f"Default is {choices[DEFAULT_CHOICE]}", choices=choices)
parser.add_argument('-a', dest='audio_only', action='store_true',
                    help='Download best quality audio only.')
parser.add_argument('-o', dest="output_dir",
                    help=f"Default is current directory.")
parser.add_argument('-r', dest="print_only", action="store_true",
                    help="Do not download, just output the generated command only.")
parser.add_argument('-i', dest="list_formats",
                    help="Print list of available formats to download.", action="store_true")
parser.add_argument('-e', dest="external_downloader",
                    help="Use aria2c as the external downloader", action="store_true")
parser.add_argument('-t', dest="is_twitch",
                    help="Custom script for twitch", action="store_true")

args = parser.parse_args()


def get_link_url(link_from_clipboard, video_quality):
    link_url = "link will be taken from clipborad"
    if link_from_clipboard:
        # TODO: Make it platform independent
        clipboard_cmd = "xclip -o -selection clipboard"
        p = subprocess.Popen(shlex.split(clipboard_cmd),
                             stdout=subprocess.PIPE)
        link_url = p.stdout.read().decode('utf-8')
    else:
        link_url = input("Enter Video URL: ")
    if video_quality is None or video_quality not in choices:
        video_quality = input(f'Enter Video Quality[{choices}]')
    return link_url, video_quality


def Main():
    link_from_clipboard, playlist_flag, video_quality, output_dir, audio_only, print_only, list_formats, external_downloader, is_twitch = (
        args.link_from_clipboard, args.playlist, args.quality, args.output_dir, args.audio_only, args.print_only, args.list_formats, args.external_downloader, args.is_twitch)
    if is_twitch:
        link = input('VOD URL: ')
        quality = input('Quality: ')
        cmd = f"youtube-dl -f {quality}"
        if external_downloader:
            cmd = f'{cmd} --external-downloader aria2c --external-downloader-args "-c -j 3 -x 3 -s 3 -k 1M"'
        cmd = f'{cmd} {link}'
        print(str(cmd))
        if not print_only:
            p = subprocess.run(shlex.split(cmd))
        exit(0)
    link_url, video_quality = get_link_url(link_from_clipboard, video_quality)
    output_dir = output_dir or current_dir
    video_quality = video_quality
    if video_quality not in choices:
        video_quality = choices[DEFAULT_CHOICE]
    video_quality = f'bestvideo[height<={video_quality[:-1]}]+bestaudio/best[height<={video_quality[:-1]}]'
    video_title = f'%(title)s.%(ext)s'
    if playlist_flag:
        video_title = f'%(playlist_index)s_{video_title}'
    if audio_only:
        video_quality = f'bestaudio'
    cmd = f'youtube-dl -f {video_quality} -o {output_dir}/{video_title} --merge-output-format {output_format} {link_url} '
    if external_downloader:
        cmd = f'{cmd} --external-downloader aria2c --external-downloader-args "-c -j 3 -x 3 -s 3 -k 1M"'
    if playlist_flag:
        cmd = f'{cmd} --yes-playlist'
    if not playlist_flag:
        cmd = f'{cmd} --no-playlist --playlist-start 1 --playlist-end 1'
    if list_formats:
        cmd = f'youtube-dl -F {link_url} --no-playlist'
    print(str(cmd))
    if not print_only:
        p = subprocess.run(shlex.split(cmd))


# run main
Main()
