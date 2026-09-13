import os
import shutil
import zipfile

from .common import FileDownloader
from .http import HttpFD
from ..postprocessor.ffmpeg import EXT_TO_OUT_FORMATS, FFmpegPostProcessor
from ..utils import PostProcessingError, determine_ext


class UgoiraFD(FileDownloader):
    """Build a video from a zip of still frames and their per-frame delays"""

    def real_download(self, filename, info_dict):
        frames = info_dict['fragments']
        ffmpeg = FFmpegPostProcessor(downloader=self.ydl)
        ffmpeg.check_version()

        tempname = self.temp_name(filename)
        zip_name = f'{tempname}.zip'
        frame_dir = f'{tempname}.frames'
        concat_file = f'{tempname}.concat'

        try:
            success, _ = HttpFD(self.ydl, self.params).download(
                zip_name, {**info_dict, 'protocol': 'https'})
            if not success:
                return False

            self.to_screen(f'[{self.FD_NAME}] Assembling {len(frames)} frames')
            with zipfile.ZipFile(zip_name) as archive:
                archive.extractall(frame_dir, [frame['path'] for frame in frames])

            files = [os.path.join(frame_dir, frame['path']) for frame in frames]
            durations = [{'duration': frame['duration']} for frame in frames]
            with open(concat_file, 'w', encoding='utf-8') as f:
                f.writelines(ffmpeg._concat_spec([*files, files[-1]], [*durations, {}]))

            ext = determine_ext(filename, 'mp4')
            try:
                ffmpeg.real_run_ffmpeg(
                    [(concat_file, ['-hide_banner', '-nostdin', '-f', 'concat', '-safe', '0'])],
                    [(tempname, ['-f', EXT_TO_OUT_FORMATS.get(ext, ext),
                                 '-fps_mode', 'vfr', '-c:v', 'copy'])])
            except PostProcessingError as e:
                self.report_error(f'Unable to assemble the frames: {e}')
                return False
        finally:
            for path in (zip_name, concat_file):
                if os.path.exists(path):
                    os.remove(path)
            shutil.rmtree(frame_dir, ignore_errors=True)

        self.try_rename(tempname, filename)
        self._hook_progress({
            'filename': filename,
            'status': 'finished',
            'total_bytes': os.path.getsize(filename),
        }, info_dict)
        return True
