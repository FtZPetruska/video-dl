import os
import re
import subprocess
from datetime import datetime
from typing import Dict, List

import ffmpeg
import PySimpleGUI as Sg

from gui import gpus_possible_encoders


def post_process_dl(full_name: str, infos: Dict) -> None:
    audio_codec = infos['acodec']
    acodecs = ["aac", "mp3", "mp4a"]
    acodec_supported = len(
        [i for i in acodecs if re.match(f"{i}", audio_codec)]) > 0
    vcodec_supported = re.match("avc1", infos['vcodec']) is not None
    _ffmpeg_video(full_name, acodec_supported, vcodec_supported, infos['fps'])


def _ffmpeg_video(path: str, acodec_supported: bool, vcodec_supported: bool, fps: int) -> None:
    recode_acodec = "aac" if not acodec_supported else "copy"
    recode_vcodec = _best_encoder(path, fps) if not vcodec_supported else "copy"
    tmp_path = os.path.splitext(path)[0] + '.tmp' + os.path.splitext(path)[1]
    ffmpegCommand = ['ffmpeg', '-hide_banner', '-i', path, '-c:a', recode_acodec, '-c:v', recode_vcodec, '-y', tmp_path]
    action = "Remuxing" if acodec_supported and vcodec_supported else "Reencoding"
    _progress_ffmpeg(ffmpegCommand, action, path)
    os.replace(tmp_path, path)


def _progress_ffmpeg(cmd: List[str], action: str, filepath: str) -> None:
    file_infos = ffmpeg.probe(filepath)['streams'][0]
    total_duration = file_infos['duration_ts'] / \
        int(file_infos['time_base'].split('/')[1])
    layout = [[Sg.Text(action)],
              [Sg.ProgressBar(100, orientation='h',
                              size=(20, 20), key='-PROG-')],
              [Sg.Text("Starting", key='PROGINFOS1')],
              [Sg.Text("", key='PROGINFOS2')],
              [Sg.Cancel()]]

    progress_window = Sg.Window(
        action, layout, no_titlebar=True, grab_anywhere=True)
    progress_pattern = re.compile(
        r'(frame|fps|size|time|bitrate|speed)\s*=\s*(\S+)')
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)

    while p.poll() is None:
        output = p.stderr.readline().rstrip(os.linesep) if p.stderr is not None else ""
        items = {key: value for key, value in progress_pattern.findall(output)}
        if items != {}:
            event, _ = progress_window.read(timeout=10)
            if event == 'Cancel' or event == Sg.WIN_CLOSED:
                progress_window.close()
                raise ValueError
            progress_percent = _get_progress_percent(
                items['time'], total_duration)
            progress_window['PROGINFOS1'].update(f"{progress_percent}%")
            progress_window['PROGINFOS2'].update(f"Speed: {items['speed']}")
            progress_window['-PROG-'].update(progress_percent)
    progress_window.close()


def _get_progress_percent(timestamp: str, total_duration: int) -> int:
    prog = re.split('[:.]', timestamp)
    progress_seconds = int(prog[0]) * 3600 + int(prog[1]) * \
        60 + int(prog[2]) + int(prog[0]) / 100
    return int(progress_seconds / total_duration * 100)


def _best_encoder(path: str, fps: int) -> str:
    output_path = path + '.tmp'
    new_input = ffmpeg.input(path, ss="00:00:00",
                             to=format(1/fps, '.3f'))
    for encoder in gpus_possible_encoders:
        try:
            (ffmpeg
             .output(new_input, path, vcodec=encoder)
             .run(overwrite_output=True))
        except ffmpeg.Error:
            continue
        else:
            return encoder
        finally:
            os.remove(path=output_path)
    return "libx264"
