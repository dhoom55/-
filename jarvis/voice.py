"""Voice: speaking (text-to-speech) and listening (speech-to-text).

Speaking tries, in order:
  1. edge-tts natural neural voices (Arabic + English) - needs internet + `pip install edge-tts`
  2. the computer's own voice, offline and with no installs:
       Windows: SAPI (System.Speech) via PowerShell
       macOS:   `say`
       Linux:   espeak-ng / espeak
Listening tries, in order:
  1. SpeechRecognition + microphone (Google, supports Arabic) - needs internet,
     `pip install SpeechRecognition pyaudio`
  2. Windows offline dictation (System.Speech, English) - no installs
Every engine can fail without breaking Jarvis: the next one is tried and the
failure is recorded for the self-healer.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from .text import is_arabic

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0   # don't flash a console from the GUI


class VoiceError(Exception):
    pass


def clean_for_speech(text: str, limit: int = 700) -> str:
    """Remove code blocks, markdown, emoji and long paths so the voice reads naturally."""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"[*_#>|•\[\]]", " ", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", " ", t)
    t = re.sub(r"(?:[A-Za-z]:)?[\\/][^\s]{20,}", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit]


def _run(args, timeout, input_text=None):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, input=input_text, creationflags=NO_WINDOW)


def _powershell(script: str, timeout: float = 120):
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        raise VoiceError("PowerShell not found")
    r = _run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout)
    if r.returncode != 0:
        raise VoiceError((r.stderr or r.stdout).strip()[-300:] or f"PowerShell exit {r.returncode}")
    return r.stdout.strip()


def _ps_quote(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


# ---------------------------------------------------------------- speaking
class Speaker:
    def __init__(self, config, healer=None):
        self.config = config
        self.healer = healer
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self.last_engine: str | None = None
        self._skip_until: dict[str, float] = {}   # engine -> time; failed engines rest for 5 min

    # -- public -------------------------------------------------------------
    def engines(self) -> list[str]:
        out = []
        if self.config["voice_online"] and self._has_edge():
            out.append("edge")
        if sys.platform == "win32" and (shutil.which("powershell") or shutil.which("pwsh")):
            out.append("sapi")
        elif sys.platform == "darwin" and shutil.which("say"):
            out.append("say")
        elif shutil.which("espeak-ng") or shutil.which("espeak"):
            out.append("espeak")
        return out

    def speak(self, text: str, to_file: Path | None = None) -> str:
        """Speak (or save to `to_file`). Returns the engine used. Raises VoiceError if all fail."""
        text = clean_for_speech(text)
        if not text:
            return "none"
        lang = "ar" if is_arabic(text) else "en"
        errors = []
        with self._lock:
            for engine in self.engines():
                if time.time() < self._skip_until.get(engine, 0):
                    continue
                try:
                    getattr(self, f"_speak_{engine}")(text, lang, to_file)
                    self.last_engine = engine
                    self._skip_until.pop(engine, None)
                    return engine
                except Exception as exc:
                    errors.append(f"{engine}: {exc}")
                    self._skip_until[engine] = time.time() + 300
                    if self.healer:
                        self.healer.record(f"voice:{engine}", exc, quiet=True)
        raise VoiceError("no voice engine worked: " + " | ".join(errors) if errors else "no voice engine available")

    def speak_async(self, text: str, on_error=None) -> threading.Thread:
        def work():
            try:
                self.speak(text)
            except Exception as exc:
                if on_error:
                    on_error(exc)
        t = threading.Thread(target=work, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        p = self._proc
        if p and p.poll() is None:
            p.kill()

    # -- engines ------------------------------------------------------------
    @staticmethod
    def _has_edge() -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def _play(self, args: list[str]) -> None:
        self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      creationflags=NO_WINDOW)
        try:
            self._proc.wait(timeout=300)
        finally:
            self._proc = None

    def _speak_edge(self, text, lang, to_file):
        import edge_tts
        voice = self.config["tts_voice_ar"] if lang == "ar" else self.config["tts_voice_en"]
        out = Path(to_file) if to_file else Path(tempfile.gettempdir()) / f"jarvis_tts_{os.getpid()}.mp3"
        if to_file and out.suffix.lower() != ".mp3":
            out = out.with_suffix(".mp3")
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

        async def save():
            await edge_tts.Communicate(text, voice, proxy=proxy).save(str(out))
        asyncio.run(asyncio.wait_for(save(), timeout=30))
        if not out.exists() or out.stat().st_size == 0:
            raise VoiceError("edge-tts produced no audio")
        if not to_file:
            self._play_mp3(out)

    def _play_mp3(self, path: Path) -> None:
        if sys.platform == "win32":
            script = ("Add-Type -AssemblyName PresentationCore; $p = New-Object System.Windows.Media.MediaPlayer; "
                      f"$p.Open([Uri]{_ps_quote(path)}); $p.Play(); $i=0; "
                      "while(-not $p.NaturalDuration.HasTimeSpan -and $i -lt 50){Start-Sleep -Milliseconds 100; $i++}; "
                      "if($p.NaturalDuration.HasTimeSpan){Start-Sleep -Milliseconds ([int]$p.NaturalDuration.TimeSpan.TotalMilliseconds + 200)}")
            exe = shutil.which("powershell") or shutil.which("pwsh")
            self._play([exe, "-NoProfile", "-NonInteractive", "-Command", script])
        elif sys.platform == "darwin":
            self._play(["afplay", str(path)])
        else:
            for player in (["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"], ["mpg123", "-q"], ["mpv", "--no-video"]):
                if shutil.which(player[0]):
                    return self._play(player + [str(path)])
            raise VoiceError("no mp3 player found (install ffmpeg or mpg123)")

    def _speak_sapi(self, text, lang, to_file):
        tmp = Path(tempfile.gettempdir()) / f"jarvis_say_{os.getpid()}.txt"
        tmp.write_text(text, encoding="utf-8")
        culture = "ar*" if lang == "ar" else "en*"
        out = f"$s.SetOutputToWaveFile({_ps_quote(Path(to_file).with_suffix('.wav'))});" if to_file else ""
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$v = $s.GetInstalledVoices() | Where-Object {{ $_.Enabled -and $_.VoiceInfo.Culture.Name -like '{culture}' }} | Select-Object -First 1; "
                  "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; "
                  f"{out} $s.Speak((Get-Content -LiteralPath {_ps_quote(tmp)} -Raw -Encoding UTF8)); $s.Dispose()")
        try:
            exe = shutil.which("powershell") or shutil.which("pwsh")
            if to_file:
                _powershell(script)
            else:
                self._play([exe, "-NoProfile", "-NonInteractive", "-Command", script])
        finally:
            tmp.unlink(missing_ok=True)

    def _speak_say(self, text, lang, to_file):
        args = ["say"]
        if lang == "ar":
            voices = _run(["say", "-v", "?"], 15).stdout
            m = re.search(r"^(\S+)\s+ar[_-]", voices, re.M)
            if m:
                args += ["-v", m.group(1)]
        if to_file:
            _run(args + ["-o", str(Path(to_file).with_suffix(".aiff")), text], 120).check_returncode()
        else:
            self._play(args + [text])

    def _speak_espeak(self, text, lang, to_file):
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        args = [exe, "-v", "ar" if lang == "ar" else "en"]
        if to_file:
            _run(args + ["-w", str(Path(to_file).with_suffix(".wav")), text], 120).check_returncode()
        else:
            self._play(args + [text])


# ---------------------------------------------------------------- listening
class Listener:
    def __init__(self, config, healer=None):
        self.config = config
        self.healer = healer
        self.last_engine: str | None = None

    def engines(self) -> list[str]:
        out = []
        if self._has_sr():
            out.append("google")
        if sys.platform == "win32" and (shutil.which("powershell") or shutil.which("pwsh")):
            out.append("sapi")
        return out

    @staticmethod
    def _has_sr() -> bool:
        try:
            import speech_recognition as sr  # noqa: F401
            import pyaudio  # noqa: F401  (microphone access)
            return True
        except ImportError:
            return False

    def listen(self, language: str | None = None, from_file: Path | None = None) -> str:
        """Record from the microphone (or a WAV file) and return the recognized text."""
        language = language or self.config["listen_language"]
        errors = []
        engines = self.engines()
        if from_file is not None:   # testing / transcribing a recording
            engines = (["google_file"] if self._has_sr_only() else []) + \
                      (["sapi"] if sys.platform == "win32" else [])
        for engine in engines:
            try:
                text = getattr(self, f"_listen_{engine}")(language, from_file).strip()
                if text:
                    self.last_engine = engine.replace("_file", "")
                    return text
                errors.append(f"{engine}: heard nothing")
            except Exception as exc:
                errors.append(f"{engine}: {exc}")
                if self.healer:
                    self.healer.record(f"voice:listen:{engine}", exc, quiet=True)
        raise VoiceError(" | ".join(errors) if errors else
                         "no speech recognizer available (pip install SpeechRecognition pyaudio)")

    @staticmethod
    def _has_sr_only() -> bool:
        try:
            import speech_recognition  # noqa: F401
            return True
        except ImportError:
            return False

    def _listen_google(self, language, from_file=None):
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=self.config["listen_seconds"], phrase_time_limit=20)
        return r.recognize_google(audio, language="ar-SA" if language == "ar" else "en-US")

    def _listen_google_file(self, language, from_file):
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.AudioFile(str(from_file)) as source:
            audio = r.record(source)
        return r.recognize_google(audio, language="ar-SA" if language == "ar" else "en-US")

    def _listen_sapi(self, language, from_file=None):
        source = (f"$r.SetInputToWaveFile({_ps_quote(from_file)})" if from_file
                  else "$r.SetInputToDefaultAudioDevice()")
        culture = "ar-SA" if language == "ar" else "en-US"
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$rec = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers(); "
                  f"$pick = $rec | Where-Object {{ $_.Culture.Name -eq '{culture}' }} | Select-Object -First 1; "
                  "if (-not $pick) { $pick = $rec | Select-Object -First 1 }; "
                  "if (-not $pick) { throw 'no offline speech recognizer is installed in Windows' }; "
                  "$r = New-Object System.Speech.Recognition.SpeechRecognitionEngine($pick); "
                  f"{source}; "
                  "$r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
                  f"$res = $r.Recognize([TimeSpan]::FromSeconds({int(self.config['listen_seconds'])})); "
                  "[Console]::OutputEncoding = [Text.Encoding]::UTF8; if ($res) { $res.Text }")
        return _powershell(script, timeout=int(self.config["listen_seconds"]) + 30)


class Voice:
    """Speaking + listening together, as used by the app."""

    def __init__(self, config, healer=None):
        self.config = config
        self.speaker = Speaker(config, healer)
        self.listener = Listener(config, healer)

    def status(self) -> str:
        speak = ", ".join(self.speaker.engines()) or "none"
        listen = ", ".join(self.listener.engines()) or "none (pip install SpeechRecognition pyaudio)"
        on = "on" if self.config["speak_replies"] else "off"
        return f"🔊 speaking engines: {speak}\n🎤 listening engines: {listen}\n🗣️ spoken replies: {on}"
