"""
High-Performance Screen & Microphone Audio Recorder for Drox Screen Studio.
Captures screen at steady 25-30 FPS using Windows GDI BitBlt + mouse cursor overlay,
records microphone audio using sounddevice, and merges them into standard H.264/AAC MP4.
"""

import os
import sys
import time
import wave
import ctypes
import threading
import subprocess
from datetime import datetime
from typing import Optional, Callable

import imageio_ffmpeg
import sounddevice as sd
import numpy as np


class ScreenRecorder:
    """
    Manages simultaneous video screen capture and microphone audio capture,
    muxing them into an MP4 file using FFmpeg.
    """
    def __init__(self, output_dir: Optional[str] = None, fps: int = 25):
        self.fps = fps
        self.output_dir = output_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
        os.makedirs(self.output_dir, exist_ok=True)

        self.ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        self.is_recording = False
        self.is_paused = False
        self.record_mic = True
        self.start_time = 0.0
        self.perf_start_time = 0.0
        self.pause_start_time = 0.0
        self.total_paused_duration = 0.0

        # Output paths
        self.current_output_file: Optional[str] = None
        self.temp_video_file: Optional[str] = None
        self.temp_audio_file: Optional[str] = None

        # Threads and processes
        self.video_thread: Optional[threading.Thread] = None
        self.video_proc: Optional[subprocess.Popen] = None
        self.audio_stream: Optional[sd.InputStream] = None
        self.audio_wave: Optional[wave.Wave_write] = None
        self._stop_event = threading.Event()

    def start_recording(self, with_mic: bool = True) -> str:
        """Starts recording screen and optional microphone audio."""
        if self.is_recording:
            return self.current_output_file or ""

        self._stop_event.clear()
        self.record_mic = with_mic
        self.start_time = time.time()
        self.perf_start_time = time.perf_counter()
        self.pause_start_time = 0.0
        self.total_paused_duration = 0.0
        self.is_recording = True
        self.is_paused = False

        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_output_file = os.path.join(self.output_dir, f"Drox_Lecture_{timestamp}.mp4")
        self.temp_video_file = os.path.join(self.output_dir, f"_temp_video_{timestamp}.mp4")
        self.temp_audio_file = os.path.join(self.output_dir, f"_temp_audio_{timestamp}.wav")

        # 1. Start audio recording if requested
        if self.record_mic:
            self._start_audio_capture()

        # 2. Start video recording thread
        self.video_thread = threading.Thread(target=self._video_record_loop, daemon=True)
        self.video_thread.start()

        return self.current_output_file

    def pause_recording(self):
        """Pauses video and microphone recording."""
        if self.is_recording and not self.is_paused:
            self.is_paused = True
            self.pause_start_time = time.perf_counter()

    def resume_recording(self):
        """Resumes video and microphone recording."""
        if self.is_recording and self.is_paused:
            self.total_paused_duration += (time.perf_counter() - self.pause_start_time)
            self.is_paused = False
            self.pause_start_time = 0.0

    def _start_audio_capture(self):
        """Initializes sounddevice audio input stream and wave writer."""
        try:
            self.audio_wave = wave.open(self.temp_audio_file, 'wb')
            self.audio_wave.setnchannels(1)
            self.audio_wave.setsampwidth(2)  # 16-bit
            self.audio_wave.setframerate(44100)

            def audio_callback(indata, frames, time_info, status):
                if self.is_recording and not self.is_paused and self.audio_wave:
                    try:
                        self.audio_wave.writeframes(indata.tobytes())
                    except Exception:
                        pass

            self.audio_stream = sd.InputStream(
                samplerate=44100,
                channels=1,
                dtype='int16',
                callback=audio_callback
            )
            self.audio_stream.start()
        except Exception as e:
            print(f"[Recorder] Audio initialization failed: {e}. Continuing video only.")
            self._cleanup_audio()

    def _cleanup_audio(self):
        """Safely stops and closes audio stream and wave file."""
        if self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except Exception:
                pass
            self.audio_stream = None

        if self.audio_wave:
            try:
                self.audio_wave.close()
            except Exception:
                pass
            self.audio_wave = None

    def _video_record_loop(self):
        """Captures screen frames and writes raw bytes to FFmpeg stdin."""
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        # Virtual screen metrics (covers entire display)
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        # H.264 requires even dimensions
        w = w - (w % 2)
        h = h - (h % 2)

        # Structure for cursor drawing
        class POINT(ctypes.Structure):
            _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

        class CURSORINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize', ctypes.c_uint32),
                ('flags', ctypes.c_uint32),
                ('hCursor', ctypes.c_void_p),
                ('ptScreenPos', POINT),
            ]

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', ctypes.c_uint32),
                ('biWidth', ctypes.c_int32),
                ('biHeight', ctypes.c_int32),
                ('biPlanes', ctypes.c_uint16),
                ('biBitCount', ctypes.c_uint16),
                ('biCompression', ctypes.c_uint32),
                ('biSizeImage', ctypes.c_uint32),
                ('biXPelsPerMeter', ctypes.c_int32),
                ('biYPelsPerMeter', ctypes.c_int32),
                ('biClrUsed', ctypes.c_uint32),
                ('biClrImportant', ctypes.c_uint32),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', ctypes.c_uint32 * 3)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h  # top-down DIB
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        gdi32.SelectObject(hdc_mem, hbm)

        buf = bytearray(w * h * 4)
        c_buf = (ctypes.c_char * len(buf)).from_buffer(buf)

        # Launch FFmpeg video encoder process
        # -preset ultrafast provides near-zero CPU overhead during live recording
        video_cmd = [
            self.ffmpeg_bin, '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{w}x{h}',
            '-pix_fmt', 'bgra',
            '-r', str(self.fps),
            '-i', '-',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '22',
            '-pix_fmt', 'yuv420p',
            self.temp_video_file
        ]

        # Hide console window on Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

        self.video_proc = subprocess.Popen(
            video_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo
        )

        frame_interval = 1.0 / self.fps
        t_start = time.perf_counter()
        frame_idx = 0

        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)

        try:
            while not self._stop_event.is_set():
                if self.is_paused:
                    time.sleep(0.04)
                    continue

                # 1. Capture screen surface (CAPTUREBLT includes transparent overlays)
                gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020 | 0x40000000)

                # 2. Draw mouse cursor if active
                try:
                    if user32.GetCursorInfo(ctypes.byref(ci)) and ci.flags == 1:
                        user32.DrawIcon(hdc_mem, ci.ptScreenPos.x, ci.ptScreenPos.y, ci.hCursor)
                except Exception:
                    pass

                # 3. Read frame buffer
                gdi32.GetDIBits(hdc_mem, hbm, 0, h, c_buf, ctypes.byref(bmi), 0)

                # 4. Pipe frame to FFmpeg
                try:
                    self.video_proc.stdin.write(buf)
                except (BrokenPipeError, OSError):
                    break

                frame_idx += 1
                # Steady frame rate pacing taking paused duration into account
                target_time = t_start + self.total_paused_duration + (frame_idx * frame_interval)
                sleep_time = target_time - time.perf_counter()
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            # Clean up Windows GDI resources
            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)

            # Close FFmpeg stdin to flush and complete encoding
            if self.video_proc and self.video_proc.stdin:
                try:
                    self.video_proc.stdin.close()
                    self.video_proc.wait(timeout=10)
                except Exception:
                    pass

    def stop_recording(self) -> Optional[str]:
        """
        Stops screen and audio recording, muxes them into the final MP4 file,
        and returns the absolute file path of the saved video.
        """
        if not self.is_recording:
            return None

        # If stopped while paused, accumulate paused duration
        if self.is_paused:
            self.total_paused_duration += (time.perf_counter() - self.pause_start_time)
            self.is_paused = False

        self.is_recording = False
        self._stop_event.set()

        # Wait for video thread
        if self.video_thread and self.video_thread.is_alive():
            self.video_thread.join(timeout=10)

        # Stop audio stream
        self._cleanup_audio()

        # Mux video + audio into final MP4 file
        final_file = self.current_output_file
        has_video = self.temp_video_file and os.path.exists(self.temp_video_file) and os.path.getsize(self.temp_video_file) > 0
        has_audio = (
            self.record_mic and
            self.temp_audio_file and
            os.path.exists(self.temp_audio_file) and
            os.path.getsize(self.temp_audio_file) > 1000
        )

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

        if has_video and has_audio:
            # Merge video and audio
            mux_cmd = [
                self.ffmpeg_bin, '-y',
                '-i', self.temp_video_file,
                '-i', self.temp_audio_file,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-shortest',
                final_file
            ]
            subprocess.run(
                mux_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo
            )
        elif has_video:
            # Video only
            try:
                if os.path.exists(final_file):
                    os.remove(final_file)
                os.rename(self.temp_video_file, final_file)
            except Exception:
                # Fallback to FFmpeg copy
                mux_cmd = [self.ffmpeg_bin, '-y', '-i', self.temp_video_file, '-c:v', 'copy', final_file]
                subprocess.run(mux_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)

        # Cleanup temporary files
        for temp_p in [self.temp_video_file, self.temp_audio_file]:
            if temp_p and os.path.exists(temp_p):
                try:
                    os.remove(temp_p)
                except Exception:
                    pass

        return final_file if (final_file and os.path.exists(final_file)) else None

    def get_duration(self) -> float:
        """Returns elapsed active recording duration in seconds (excluding paused time)."""
        if not self.is_recording:
            return 0.0
        if self.is_paused:
            current_paused = time.perf_counter() - self.pause_start_time
        else:
            current_paused = 0.0
        return max(0.0, time.perf_counter() - self.perf_start_time - self.total_paused_duration - current_paused)
