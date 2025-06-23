#!/usr/bin/python3
# helper code for using youtube-dl
# almost complete, just testing is remaining. Should be useful by now.
from argparse import ArgumentParser
from pprint import pprint
import shlex
import os
import subprocess

# constants
choices = ['240p', '360p', '480p', '720p', '1080p', '1440p']
current_dir = os.path.abspath(os.curdir)
DEFAULT_CHOICE = 4
output_format = 'mp4'

IS_WINDOWS = os.name == 'nt'
IS_ANDROID = False

# check if script is running on Android (because we need distinguish android from linux when using clipboard)
if not IS_WINDOWS:
    uname_o = subprocess.Popen(shlex.split(
        'uname -o'), stdout=subprocess.PIPE).stdout.read().decode('utf-8').strip()
    IS_ANDROID = uname_o == 'Android'

# CLI Parser
parser = ArgumentParser(description="Helper wrapper around youtube-dl for easier usage.")
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
parser.add_argument('-l', dest="link_from_args",
                    help="Link to the youtube URL")

args = parser.parse_args()

# windows specific code to access clipboard
user32 = None
if IS_WINDOWS:
    import ctypes
    CF_TEXT = 1
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32 = ctypes.windll.user32
    user32.GetClipboardData.restype = ctypes.c_void_p

# stolen from https://stackoverflow.com/a/23285159


def get_clipboard_text_windows(user32):
    if not user32:
        print('You are not on windows / clipboard is not accesible.')
        print('Abort.')
        exit(1)

    user32.OpenClipboard(0)
    try:
        if user32.IsClipboardFormatAvailable(CF_TEXT):
            data = user32.GetClipboardData(CF_TEXT)
            data_locked = kernel32.GlobalLock(data)
            text = ctypes.c_char_p(data_locked)
            value = text.value
            kernel32.GlobalUnlock(data_locked)
            return value.decode('utf-8')
    finally:
        user32.CloseClipboard()


# termux-clipboard-get doesn't work on Android 7.0 and probably prior, so fallback to stdin
def get_clipboard_text_android():
    res = subprocess.run(shlex.split('termux-clipboard-get'),
                         stdout=subprocess.PIPE, timeout=1)
    return res.stdout.decode('utf-8')


def get_link_url(link_from_args, link_from_clipboard, video_quality):
    ''' Get link and video quality.
            Determines if link is to be copied from clipboard, and if the video quality is valid, otherwise asks user about the same through stdin.
        Agruments:
            `link_from_clipboard` -- if the link should be taken from clipboard (Boolean) 
            `video_quality` -- video quality that should be checked for validation
    '''
    link_url = "link will be taken from clipborad"
    if link_from_args:
        link_url = link_from_args
    elif link_from_clipboard:
        clipboard_cmd = "xclip -o -selection clipboard"
        try:
            if IS_WINDOWS:
                link_url = get_clipboard_text_windows(user32)
            elif IS_ANDROID:
                link_url = get_clipboard_text_android()
            else:
                res = subprocess.run(shlex.split(clipboard_cmd),
                                     stdout=subprocess.PIPE, timeout=1)
                link_url = res.stdout.decode('utf-8')
        except:
            print('Clipboard access not available.')
            link_url = input('Enter Video URL: ')
    else:
        link_url = input("Enter Video URL: ")
    if video_quality is None or video_quality not in choices:
        video_quality = str(input(f'Enter Video Quality[{choices}]: '))
    return link_url, video_quality


def Main():
    # mapping arguments to variables
    link_from_args, link_from_clipboard, playlist_flag, video_quality, output_dir, audio_only, print_only, list_formats, external_downloader, is_twitch = (
        args.link_from_args, args.link_from_clipboard, args.playlist, args.quality, args.output_dir, args.audio_only, args.print_only, args.list_formats, args.external_downloader, args.is_twitch)

    if is_twitch:
        # twitch specific special flags
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

    # prepare video url and quality
    link_url, video_quality = get_link_url(
        link_from_args, link_from_clipboard, video_quality)

    # prepare output directory
    output_dir = output_dir or current_dir

    # prepare video quality
    if video_quality not in choices:
        # user managed to enter wrong quality so we reset to default choice instead of exiting
        video_quality = choices[DEFAULT_CHOICE]

    video_quality = f'bestvideo[height<={video_quality[:-1]}]+bestaudio/best[height<={video_quality[:-1]}]'

    if audio_only:
        video_quality = f'bestaudio'

    # prepare video title
    video_title = f'%(title)s.%(ext)s'

    if playlist_flag:
        video_title = f'%(playlist_index)s_{video_title}'

    # prepare youtube-dl command
    cmd = f'youtube-dl -f {video_quality} -o {output_dir}/{video_title} --merge-output-format {output_format} {link_url}'

    # self-explanatory flags
    if external_downloader:
        cmd = f'{cmd} --external-downloader aria2c --external-downloader-args "-c -j 3 -x 3 -s 3 -k 1M"'
    if playlist_flag:
        cmd = f'{cmd} --yes-playlist'
    if not playlist_flag:
        cmd = f'{cmd} --no-playlist --playlist-start 1 --playlist-end 1'
    if list_formats:
        cmd = f'youtube-dl -F {link_url} --no-playlist'

    # print the generated command
    print(str(cmd))

    if not print_only:
        # actually run the command
        p = subprocess.run(shlex.split(cmd))


# run Main
Main()
