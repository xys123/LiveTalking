"""Windows SAPI5 bridge for LiveTalking running inside WSL."""
import os
import subprocess
import tempfile

import numpy as np
import resampy
import soundfile as sf

from registry import register
from utils.logger import logger
from .base_tts import BaseTTS, State


@register("tts", "winsapi")
class WindowsSapiTTS(BaseTTS):
    """Synthesize to a WAV with Windows SAPI, then feed the WSL avatar pipeline."""

    def txt_to_audio(self, msg: tuple[str, dict]):
        text, textevent = msg
        wav_path = None
        try:
            fd, wav_path = tempfile.mkstemp(prefix="livetalking-sapi-", suffix=".wav")
            os.close(fd)
            win_path = subprocess.check_output(["wslpath", "-w", wav_path], text=True).strip()
            bridge_path = subprocess.check_output(
                ["wslpath", "-w", os.path.join(os.path.dirname(__file__), "winsapi_bridge.ps1")], text=True
            ).strip()
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-File", bridge_path, "-Text", text, "-Path", win_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=90,
                check=False,
            )
            if result.returncode != 0 or not os.path.getsize(wav_path):
                detail = result.stderr.decode("gbk", errors="replace").strip()
                raise RuntimeError(detail or "Windows SAPI did not create a WAV file")
            stream = self._read_wav(wav_path)
            self._enqueue_audio(stream, text, textevent)
        except Exception:
            logger.exception("winsapi tts")
        finally:
            if wav_path:
                try:
                    os.unlink(wav_path)
                except FileNotFoundError:
                    pass

    def _read_wav(self, path: str) -> np.ndarray:
        stream, sample_rate = sf.read(path, dtype="float32")
        if stream.ndim > 1:
            stream = stream[:, 0]
        if sample_rate != self.sample_rate and stream.size:
            stream = resampy.resample(stream, sr_orig=sample_rate, sr_new=self.sample_rate)
        return stream.astype(np.float32, copy=False)

    def _enqueue_audio(self, stream: np.ndarray, text: str, textevent: dict) -> None:
        idx = 0
        remaining = stream.shape[0]
        while remaining >= self.chunk and self.state == State.RUNNING:
            eventpoint = {}
            remaining -= self.chunk
            if idx == 0:
                eventpoint = {"status": "start", "text": text}
            elif remaining < self.chunk:
                eventpoint = {"status": "end", "text": text}
            eventpoint.update(**textevent)
            self.parent.put_audio_frame(stream[idx:idx + self.chunk], eventpoint)
            idx += self.chunk



