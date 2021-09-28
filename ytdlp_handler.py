import mimetypes
from typing import Any, Dict

import yt_dlp
from quantiphy import Quantity

from ffmpeg_handler import *
from lang import GuiField, get_text

CANCELED = False


def video_dl(values: Dict) -> None:
    global CANCELED
    CANCELED = False
    trim_start = f"{values['sH']}:{values['sM']}:{values['sS']}"
    trim_end = f"{values['eH']}:{values['eM']}:{values['eS']}"
    ydl_opts = _gen_query(values['MaxHeight'], values['Browser'],
                          values['AudioOnly'], values['path'], trim_start, trim_end)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        infos_ydl = ydl.extract_info(values["url"])
    ext = 'mp3' if values['AudioOnly'] else infos_ydl['ext']
    full_path = os.path.splitext(ydl.prepare_filename(infos_ydl))[
        0] + '.' + ext
    if not values['AudioOnly']:
        post_process_dl(full_path, infos_ydl)


def _gen_query(h: int, browser: str, audio_only: bool, path: str, start: str, end: str) -> Dict[str, Any]:
    options = {'noplaylist': True, 'overwrites': True, 'progress_hooks': [download_progress_bar],
               'trim_file_name': 250, 'outtmpl': os.path.join(path, "%(title).100s - %(uploader)s.%(ext)s")}
    video_format = ""
    acodecs = ["aac", "mp3"] if audio_only else ["aac", "mp3", "mp4a"]
    for acodec in acodecs:
        video_format += f'bestvideo[vcodec*=avc1][height<=?{h}]+bestaudio[acodec*={acodec}]/'
    video_format += f'bestvideo[vcodec*=avc1][height<=?{h}]+bestaudio/'
    for acodec in ["aac", "mp3", "mp4a"]:
        video_format += f'/bestvideo[height<=?{h}]bestaudio[acodec={acodec}]/'
    video_format += f'bestvideo[height<=?{h}]bestaudio/best'
    audio_format = 'bestaudio[acodec*=mp3]/bestaudio/best'
    options['format'] = audio_format if audio_only else video_format
    if audio_only:
        options['extract_audio'] = True
        options['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }]
    if start != "00:00:00" or end != "99:59:59":
        options['external_downloader'] = 'ffmpeg'
        options['external_downloader_args'] = {
            'ffmpeg_i': ['-ss', start, '-to', end]}
    elif not audio_only:
        options["merge-output-format"] = "mp4"
    if browser != "None":
        options['cookiesfrombrowser'] = [browser.lower()]
    return options


def download_progress_bar(d):
    global CANCELED
    media_type = mimetypes.guess_type(d['filename'])[0].split('/')[0]
    if d['status'] == 'finished':
        file_tuple = os.path.split(os.path.abspath(d['filename']))
        print("Done downloading {}".format(file_tuple[1]))
    if d['status'] == 'downloading':
        downloaded = Quantity(d['downloaded_bytes'], 'B')
        total = Quantity(d['total_bytes'], 'B') if 'total_bytes' in d.keys(
        ) else Quantity(d['total_bytes_estimate'], 'B')
        progress = Sg.OneLineProgressMeter(get_text(GuiField.ytdlp_downloading), downloaded,
                                           total, f'{get_text(GuiField.ytdlp_downloading)} {media_type}',
                                           orientation='h', no_titlebar=True, grab_anywhere=True)
        if CANCELED or (not progress and downloaded < total):
            CANCELED = True
            raise ValueError
