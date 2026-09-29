#!/usr/bin/env python3
"""Mic Fixer — a native microphone checker for PipeWire.

No browser, no webview: GTK4 + libadwaita for the UI, GStreamer for audio.

Capture is `pulsesrc ! audioconvert ! appsink`, pulled into a numpy buffer. The
live meter, the waveform, the verdict and the WAV that gets played back are all
derived from that one buffer, so the numbers on screen are the numbers in the
file. Playback is `playbin` on the written WAV.

  mic-fixer                       open the window
  mic-fixer --list-devices        print real capture sources, one per line
  mic-fixer --probe [--device N] [--seconds S] [--json] [--wav PATH]
                                  headless capture + analysis through the same
                                  Recorder/analyse code path the GUI uses

In the window: Ctrl+R record/stop, Ctrl+P play/pause, Ctrl+D or F5 re-scan
devices, Ctrl+Q quit. Those are GApplication actions, so they are also callable
over the session bus (`gdbus call --dest dev.jan.MicFixer …`).
"""

from __future__ import annotations

import argparse
import atexit
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import wave

import numpy as np

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gst, Gtk  # noqa: E402

try:                                   # GLib 2.86 moved the unix helpers out
    gi.require_version("GLibUnix", "2.0")
    from gi.repository import GLibUnix  # noqa: E402
    unix_signal_add = GLibUnix.signal_add
except (ValueError, ImportError):      # pragma: no cover - older GLib
    unix_signal_add = GLib.unix_signal_add

APP_ID = "dev.jan.MicFixer"
RATE = 48000
HOP = 512                 # samples per envelope column (~10.7 ms at 48 kHz)
MAX_SECONDS = 30
LIVE_WINDOW_S = 6.0       # seconds of scrolling envelope shown while recording

DB_FLOOR = -70.0          # bottom of every dB scale in the UI


# --------------------------------------------------------------------------- #
# Devices
# --------------------------------------------------------------------------- #

class Device:
    def __init__(self, name: str, description: str, channels: int, rate: int):
        self.name = name
        self.description = description
        self.channels = channels
        self.rate = rate

    @property
    def is_virtual(self) -> bool:
        # EasyEffects (and similar) expose a processed virtual source. It is a
        # usable input, unlike a .monitor, but it is not a physical mic either.
        return not self.name.startswith("alsa_input.")

    def label(self) -> str:
        suffix = "  (virtual)" if self.is_virtual else ""
        return f"{self.description}{suffix}"


def list_devices() -> list[Device]:
    """Real capture sources only.

    `.monitor` sources are loopbacks of an output, not microphones — Jan runs
    EasyEffects, so `easyeffects_sink.monitor` shows up in the raw list and is
    emphatically not a mic. Everything ending in `.monitor` is dropped.
    """
    try:
        out = subprocess.run(
            ["pactl", "-f", "json", "list", "sources"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    try:
        raw = json.loads(out.stdout)
    except (ValueError, TypeError):
        return []

    devices = []
    for src in raw:
        name = src.get("name") or ""
        if not name or name.endswith(".monitor"):
            continue
        props = src.get("properties") or {}
        desc = (src.get("description")
                or props.get("device.description")
                or name)
        spec = src.get("sample_specification") or ""
        channels, rate = 1, RATE
        for token in spec.split():
            if token.endswith("ch"):
                try:
                    channels = int(token[:-2])
                except ValueError:
                    pass
            elif token.endswith("Hz"):
                try:
                    rate = int(token[:-2])
                except ValueError:
                    pass
        devices.append(Device(name, desc, channels, rate))

    devices.sort(key=lambda d: (d.is_virtual, d.description.lower()))
    return devices


def default_source() -> str | None:
    try:
        out = subprocess.run(["pactl", "info"], capture_output=True,
                             text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in out.stdout.splitlines():
        if line.startswith("Default Source:"):
            return line.split(":", 1)[1].strip()
    return None


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #

def dbfs(x: float) -> float:
    return 20.0 * math.log10(x) if x > 1e-9 else DB_FLOOR - 30.0


class Analysis:
    """Verdict plus the measured numbers behind it."""

    def __init__(self, samples: np.ndarray, rate: int = RATE):
        self.rate = rate
        self.duration = samples.size / float(rate) if rate else 0.0
        self.n_samples = int(samples.size)

        if samples.size == 0:
            self.peak = self.rms = 0.0
            self.peak_db = self.rms_db = DB_FLOOR - 30.0
            self.noise_db = self.speech_db = DB_FLOOR - 30.0
            self.snr = 0.0
            self.clipped = 0
            self.clipped_pct = 0.0
            self.silent_pct = 100.0
            self.dc_offset = 0.0
            self.verdict = "no audio"
            self.severity = "warn"
            self.detail = "Nothing was captured."
            return

        self.peak = float(np.abs(samples).max())
        self.rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
        self.peak_db = dbfs(self.peak)
        self.rms_db = dbfs(self.rms)
        self.dc_offset = float(samples.mean())

        # A sample at full scale is the digital ceiling; count how often we sit
        # on it rather than testing peak alone, so a single stray spike does not
        # read the same as sustained clipping.
        self.clipped = int(np.count_nonzero(np.abs(samples) >= 0.999))
        self.clipped_pct = 100.0 * self.clipped / samples.size

        # Frame energies: the quiet tail is the noise floor, the loud tail is
        # whatever was actually said into the mic.
        frame = max(1, rate // 100)              # 10 ms frames
        usable = (samples.size // frame) * frame
        if usable >= frame:
            frames = samples[:usable].reshape(-1, frame).astype(np.float64)
            energies = np.sqrt((frames ** 2).mean(axis=1))
        else:
            energies = np.array([self.rms])
        self.noise_db = dbfs(float(np.percentile(energies, 10)))
        self.speech_db = dbfs(float(np.percentile(energies, 90)))
        self.snr = self.speech_db - self.noise_db

        # Digital silence, as opposed to a quiet room. A mic that is actually
        # connected always has *some* self-noise, so exact zeros mean the
        # device stopped delivering — pull the USB cable mid-take and PipeWire
        # keeps the stream open and pads it with nothing. Without this, that
        # padding drags the p10 noise floor to the numeric floor and the take
        # scores as unusually clean.
        self.silent_pct = 100.0 * float(np.mean(energies < 1e-6))

        self.verdict, self.severity, self.detail = self._judge()

    def _judge(self) -> tuple[str, str, str]:
        if self.silent_pct >= 20.0:
            return ("dropouts", "bad",
                    f"{self.silent_pct:.0f}% of the take is digital silence, "
                    "not room tone — the device stopped delivering audio "
                    "part-way through. Check the cable, the USB port, or "
                    "whether something else grabbed the mic.")

        if self.clipped_pct >= 0.01 or self.peak_db >= -0.5:
            return ("clipping", "bad",
                    f"{self.clipped} samples pinned at full scale "
                    f"({self.clipped_pct:.3f}%), peak {self.peak_db:+.1f} dBFS. "
                    "Turn the input gain down until peaks land near -6 dBFS.")

        if self.speech_db < -40.0:
            return ("too quiet", "bad",
                    f"Loud passages only reach {self.speech_db:+.1f} dBFS. "
                    "Either nothing was said, or the gain is far too low — "
                    "aim for -18 to -12 dBFS while speaking.")

        if self.noise_db > -50.0 or self.snr < 20.0:
            return ("high noise floor", "warn",
                    f"Noise floor {self.noise_db:+.1f} dBFS against "
                    f"{self.speech_db:+.1f} dBFS of signal — only "
                    f"{self.snr:.1f} dB of headroom over the room. "
                    "Look for fans, a gain-heavy preamp, or a hissy USB port.")

        if self.peak_db > -3.0:
            return ("healthy", "warn",
                    f"Clean, but peaks at {self.peak_db:+.1f} dBFS leave very "
                    "little headroom. A slight gain trim would be safer.")

        return ("healthy", "good",
                f"Peak {self.peak_db:+.1f} dBFS, speech {self.speech_db:+.1f} "
                f"dBFS, noise floor {self.noise_db:+.1f} dBFS "
                f"({self.snr:.1f} dB SNR), no clipped samples.")

    def rows(self) -> list[tuple[str, str]]:
        return [
            ("Duration", f"{self.duration:.2f} s  ({self.n_samples} samples "
                         f"@ {self.rate} Hz)"),
            ("Peak", f"{self.peak_db:+.1f} dBFS"),
            ("RMS", f"{self.rms_db:+.1f} dBFS"),
            ("Speech level (p90)", f"{self.speech_db:+.1f} dBFS"),
            ("Noise floor (p10)", f"{self.noise_db:+.1f} dBFS"),
            ("Signal-to-noise", f"{self.snr:.1f} dB"),
            ("Clipped samples", f"{self.clipped}  ({self.clipped_pct:.3f}%)"),
            ("Digital silence", f"{self.silent_pct:.1f}% of the take"),
            ("DC offset", f"{self.dc_offset:+.5f}"),
        ]

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "severity": self.severity,
            "detail": self.detail,
            "duration_s": round(self.duration, 3),
            "samples": self.n_samples,
            "rate": self.rate,
            "peak_dbfs": round(self.peak_db, 2),
            "rms_dbfs": round(self.rms_db, 2),
            "speech_dbfs": round(self.speech_db, 2),
            "noise_floor_dbfs": round(self.noise_db, 2),
            "snr_db": round(self.snr, 2),
            "clipped_samples": self.clipped,
            "clipped_pct": round(self.clipped_pct, 5),
            "digital_silence_pct": round(self.silent_pct, 2),
            "dc_offset": round(self.dc_offset, 6),
        }


def write_wav(path: str, samples: np.ndarray, rate: int = RATE) -> None:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------- #
# Capture
# --------------------------------------------------------------------------- #

class Recorder:
    """Mono 48 kHz capture from a named PulseAudio/PipeWire source.

    Samples are accumulated in memory; an envelope of (min, max, rms) per HOP
    samples is built as we go so the UI never has to rescan the full take.

    Callbacks all fire on the GLib main loop:
      on_level(rms_db, peak_db, new_columns)  every chunk while recording
      on_stop(samples, envelope, error)       once, when capture ends
    """

    def __init__(self, device: str, on_level=None, on_stop=None,
                 max_seconds: int = MAX_SECONDS):
        self.device = device
        self.on_level = on_level
        self.on_stop = on_stop
        self.max_seconds = max_seconds

        self._chunks: list[np.ndarray] = []
        self._tail = np.zeros(0, dtype=np.float32)   # < HOP leftover
        self.envelope: list[tuple[float, float, float]] = []
        self.n_samples = 0

        self._pipeline = None
        self._bus_id = None
        self._timeout_id = None
        self._finished = False
        self.error: str | None = None

    # -- lifecycle ---------------------------------------------------------- #

    def start(self) -> None:
        desc = (
            f'pulsesrc name=src device="{self.device}" '
            "! audioconvert ! audioresample "
            f"! audio/x-raw,format=S16LE,rate={RATE},channels=1,"
            "layout=interleaved "
            "! appsink name=sink emit-signals=true sync=false "
            "max-buffers=100 drop=false"
        )
        self._pipeline = Gst.parse_launch(desc)
        sink = self._pipeline.get_by_name("sink")
        sink.connect("new-sample", self._on_sample)

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        self._bus_id = bus.connect("message", self._on_message)

        ret = self._pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            self._finish("Could not open the capture device.")
            return

        self._timeout_id = GLib.timeout_add_seconds(
            self.max_seconds, self._on_max_length)

    def stop(self) -> None:
        self._finish(None)

    # -- internals ---------------------------------------------------------- #

    def _on_max_length(self) -> bool:
        self._timeout_id = None
        self._finish(None)
        return False

    def _on_sample(self, sink) -> Gst.FlowReturn:
        sample = sink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK
        buf = sample.get_buffer()
        ok, info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.OK
        try:
            data = np.frombuffer(bytes(info.data), dtype="<i2")
        finally:
            buf.unmap(info)
        if data.size == 0:
            return Gst.FlowReturn.OK
        block = (data.astype(np.float32) / 32768.0)
        GLib.idle_add(self._consume, block)
        return Gst.FlowReturn.OK

    def _consume(self, block: np.ndarray) -> bool:
        if self._finished:
            return False
        self._chunks.append(block)
        self.n_samples += block.size

        work = np.concatenate((self._tail, block)) if self._tail.size else block
        n_cols = work.size // HOP
        new_cols = []
        if n_cols:
            cols = work[: n_cols * HOP].reshape(n_cols, HOP)
            mins = cols.min(axis=1)
            maxs = cols.max(axis=1)
            rmss = np.sqrt((cols.astype(np.float64) ** 2).mean(axis=1))
            for i in range(n_cols):
                col = (float(mins[i]), float(maxs[i]), float(rmss[i]))
                self.envelope.append(col)
                new_cols.append(col)
        self._tail = work[n_cols * HOP:].copy()

        if self.on_level:
            peak = float(np.abs(block).max())
            rms = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
            self.on_level(dbfs(rms), dbfs(peak), new_cols)
        return False

    def _on_message(self, bus, message) -> None:
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, _debug = message.parse_error()
            # This is the unplugged-USB-mic path: pulsesrc errors out, we keep
            # whatever was already captured instead of taking the app down.
            self._finish(err.message or "The capture device failed.")
        elif t == Gst.MessageType.EOS:
            self._finish(None)

    def _finish(self, error: str | None) -> None:
        if self._finished:
            return
        self._finished = True
        self.error = error

        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        if self._pipeline is not None:
            bus = self._pipeline.get_bus()
            if self._bus_id is not None:
                bus.disconnect(self._bus_id)
                self._bus_id = None
            bus.remove_signal_watch()
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None

        # Fold the sub-HOP remainder in so short takes still draw something.
        if self._tail.size:
            self.envelope.append((float(self._tail.min()),
                                  float(self._tail.max()),
                                  float(np.sqrt((self._tail.astype(np.float64)
                                                 ** 2).mean()))))
            self._tail = np.zeros(0, dtype=np.float32)

        samples = (np.concatenate(self._chunks) if self._chunks
                   else np.zeros(0, dtype=np.float32))
        self._chunks = []
        if self.on_stop:
            GLib.idle_add(self.on_stop, samples, self.envelope, error)


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #

def _colors(dark: bool) -> dict:
    if dark:
        return {
            "bg": (0.13, 0.13, 0.15),
            "grid": (1, 1, 1, 0.08),
            "wave": (0.45, 0.70, 1.00),
            "wave_soft": (0.45, 0.70, 1.00, 0.35),
            "cursor": (1.00, 0.84, 0.35),
            "text": (1, 1, 1, 0.55),
        }
    return {
        "bg": (0.97, 0.97, 0.98),
        "grid": (0, 0, 0, 0.08),
        "wave": (0.14, 0.42, 0.78),
        "wave_soft": (0.14, 0.42, 0.78, 0.35),
        "cursor": (0.80, 0.45, 0.05),
        "text": (0, 0, 0, 0.55),
    }


def _is_dark() -> bool:
    return Adw.StyleManager.get_default().get_dark()


class Waveform(Gtk.DrawingArea):
    """Envelope view. Scrolls while recording; click-to-seek once idle."""

    def __init__(self, on_seek=None):
        super().__init__()
        self.set_content_height(170)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

        self.envelope: list[tuple[float, float, float]] = []
        self.live = False
        self.cursor: float | None = None     # 0..1 playback position
        self.on_seek = on_seek

        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer", None))

    def set_envelope(self, envelope, live=False):
        self.envelope = envelope
        self.live = live
        self.queue_draw()

    def set_cursor_fraction(self, fraction: float | None):
        self.cursor = fraction
        self.queue_draw()

    def clear(self):
        self.envelope = []
        self.live = False
        self.cursor = None
        self.queue_draw()

    def _on_click(self, gesture, n_press, x, y):
        if self.live or not self.envelope or self.on_seek is None:
            return
        width = max(1, self.get_width())
        self.on_seek(min(1.0, max(0.0, x / width)))

    def _draw(self, area, cr, width, height):
        c = _colors(_is_dark())
        cr.set_source_rgb(*c["bg"])
        cr.rectangle(0, 0, width, height)
        cr.fill()

        mid = height / 2.0

        # -6 / -12 dBFS guide lines plus the centre line.
        cr.set_line_width(1)
        cr.set_source_rgba(*c["grid"])
        for frac in (1.0, 0.501, 0.251):          # 0, -6, -12 dBFS
            for sign in (-1, 1):
                y = mid + sign * frac * (mid - 4)
                cr.move_to(0, y + 0.5)
                cr.line_to(width, y + 0.5)
        cr.move_to(0, mid + 0.5)
        cr.line_to(width, mid + 0.5)
        cr.stroke()

        if not self.envelope:
            cr.set_source_rgba(*c["text"])
            cr.select_font_face("sans")
            cr.set_font_size(13)
            msg = "No take yet — hit Record."
            ext = cr.text_extents(msg)
            cr.move_to((width - ext.width) / 2, mid + 5)
            cr.show_text(msg)
            return

        env = self.envelope
        if self.live:
            # Scroll: only the most recent LIVE_WINDOW_S of columns.
            visible = int(LIVE_WINDOW_S * RATE / HOP)
            env = env[-visible:]
            cols = min(width, max(1, len(env)))
        else:
            cols = width

        scale = mid - 4
        # Bucket the envelope into one column per pixel.
        n = len(env)
        cr.set_source_rgba(*c["wave_soft"])
        peaks = []
        for px in range(cols):
            a = int(px * n / cols)
            b = max(a + 1, int((px + 1) * n / cols))
            chunk = env[a:b]
            lo = min(v[0] for v in chunk)
            hi = max(v[1] for v in chunk)
            rms = max(v[2] for v in chunk)
            peaks.append(rms)
            y0 = mid - hi * scale
            y1 = mid - lo * scale
            if y1 - y0 < 1:
                y1 = y0 + 1
            cr.rectangle(px, y0, 1, y1 - y0)
        cr.fill()

        # RMS body drawn on top, so quiet-but-busy takes still read clearly.
        cr.set_source_rgb(*c["wave"])
        for px, rms in enumerate(peaks):
            h = max(1.0, rms * scale)
            cr.rectangle(px, mid - h, 1, h * 2)
        cr.fill()

        if self.cursor is not None and not self.live:
            x = self.cursor * width
            cr.set_source_rgb(*c["cursor"])
            cr.set_line_width(2)
            cr.move_to(x, 0)
            cr.line_to(x, height)
            cr.stroke()


class LevelMeter(Gtk.DrawingArea):
    """Horizontal dB bar with a decaying peak-hold tick."""

    def __init__(self):
        super().__init__()
        self.set_content_height(26)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)
        self.rms_db = DB_FLOOR
        self.peak_db = DB_FLOOR
        self._hold_db = DB_FLOOR

    def set_levels(self, rms_db: float, peak_db: float):
        self.rms_db = rms_db
        self.peak_db = peak_db
        self._hold_db = max(peak_db, self._hold_db - 1.5)
        self.queue_draw()

    def reset(self):
        self.rms_db = self.peak_db = self._hold_db = DB_FLOOR
        self.queue_draw()

    @staticmethod
    def _frac(db: float) -> float:
        return min(1.0, max(0.0, (db - DB_FLOOR) / (0.0 - DB_FLOOR)))

    def _draw(self, area, cr, width, height):
        dark = _is_dark()
        cr.set_source_rgba(1, 1, 1, 0.07) if dark else \
            cr.set_source_rgba(0, 0, 0, 0.07)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        w = self._frac(self.rms_db) * width
        # Green to -12, amber to -3, red above: the usual broadcast bands.
        for x0, x1, rgb in (
            (0.0, self._frac(-12.0) * width, (0.30, 0.75, 0.40)),
            (self._frac(-12.0) * width, self._frac(-3.0) * width,
             (0.95, 0.72, 0.20)),
            (self._frac(-3.0) * width, width, (0.90, 0.30, 0.28)),
        ):
            if w <= x0:
                break
            cr.set_source_rgb(*rgb)
            cr.rectangle(x0, 0, min(w, x1) - x0, height)
            cr.fill()

        if self._hold_db > DB_FLOOR:
            x = self._frac(self._hold_db) * width
            cr.set_source_rgba(1, 1, 1, 0.9) if dark else \
                cr.set_source_rgba(0, 0, 0, 0.7)
            cr.rectangle(max(0, x - 1), 0, 2, height)
            cr.fill()

        cr.set_source_rgba(*(( 1, 1, 1, 0.35) if dark else (0, 0, 0, 0.35)))
        cr.set_line_width(1)
        cr.select_font_face("sans")
        cr.set_font_size(9)
        for db in (-60, -48, -36, -24, -12, -6, 0):
            x = self._frac(db) * width
            cr.move_to(x + 0.5, height - 7)
            cr.line_to(x + 0.5, height)
            cr.stroke()
            cr.move_to(min(x + 2, width - 16), 9)
            cr.show_text(str(db))


# --------------------------------------------------------------------------- #
# Window
# --------------------------------------------------------------------------- #

class MicFixerWindow(Adw.ApplicationWindow):
    def __init__(self, app, preferred_device: str | None = None):
        super().__init__(application=app, title="Mic Fixer")
        # Deliberately small: this is a check-and-close utility, not something you
        # keep open, so it should sit over your work rather than displace it. The
        # waveform is a fixed 170px and the meter 26px; everything else is text and
        # controls inside a ScrolledWindow, so a shorter window scrolls rather than
        # clipping, and nothing in the layout has a fixed width to squeeze.
        #
        # Where it *opens* is not ours to choose. Wayland gives a client no way to
        # position its own toplevel — no move(), no screen coords — so "centre of
        # the screen" and "draggable" are both compositor-side. They live in
        # ~/.config/hypr/hyprland.lua as a window rule matching class dev.jan.MicFixer:
        # `float = true` (a tiled window can't be dragged) plus `center = true`.
        self.set_default_size(560, 620)

        self.preferred_device = preferred_device
        self.devices: list[Device] = []
        self.recorder: Recorder | None = None
        self.samples = np.zeros(0, dtype=np.float32)
        self.analysis: Analysis | None = None
        self.player = None
        self._player_bus_id = None
        self._pos_timer = None
        self._rec_timer = None
        self._device_poll = None
        # The scratch take lives under XDG_RUNTIME_DIR when there is one: that
        # is a tmpfs the session owns, so even a SIGKILL leaves nothing behind
        # after logout. _on_close and the atexit hook handle the normal case.
        self._scratch = tempfile.mkdtemp(
            prefix="mic-fixer-", dir=os.environ.get("XDG_RUNTIME_DIR") or None)
        self.wav_path = os.path.join(self._scratch, "take.wav")
        atexit.register(self._clean_scratch)

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toasts.set_child(root)

        header = Adw.HeaderBar()
        self.refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        self.refresh_btn.set_tooltip_text("Re-scan input devices")
        self.refresh_btn.connect("clicked", lambda *_: self.reload_devices(True))
        header.pack_end(self.refresh_btn)
        root.append(header)

        self.banner = Adw.Banner(revealed=False)
        self.banner.set_button_label("Re-scan")
        self.banner.connect("button-clicked",
                            lambda *_: self.reload_devices(True))
        root.append(self.banner)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        root.append(scroller)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        page.set_margin_top(18)
        page.set_margin_bottom(24)
        page.set_margin_start(18)
        page.set_margin_end(18)
        scroller.set_child(page)

        # --- input ---------------------------------------------------------- #
        input_group = Adw.PreferencesGroup(title="Input")
        self.device_row = Adw.ComboRow(title="Microphone")
        self.device_row.set_subtitle("Capture sources only — monitors excluded")
        self.device_model = Gtk.StringList()
        self.device_row.set_model(self.device_model)
        self.device_row.connect("notify::selected", self._on_device_changed)
        input_group.add(self.device_row)
        page.append(input_group)

        # --- meter + transport ---------------------------------------------- #
        meter_group = Adw.PreferencesGroup(title="Level")
        meter_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        meter_box.set_margin_top(6)
        meter_box.set_margin_bottom(12)
        meter_box.set_margin_start(12)
        meter_box.set_margin_end(12)

        self.meter = LevelMeter()
        meter_box.append(self.meter)

        self.level_label = Gtk.Label(xalign=0)
        self.level_label.add_css_class("dim-label")
        self.level_label.add_css_class("caption")
        self.level_label.set_text("Idle — no signal")
        meter_box.append(self.level_label)

        meter_group.add(meter_box)
        page.append(meter_group)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        controls.set_halign(Gtk.Align.CENTER)

        self.record_btn = Gtk.Button()
        self.record_btn.set_tooltip_text("Start / stop the test recording "
                                        "(Ctrl+R)")
        self._set_record_idle()
        self.record_btn.add_css_class("pill")
        self.record_btn.add_css_class("suggested-action")
        self.record_btn.connect("clicked", self._on_record_clicked)
        controls.append(self.record_btn)

        self.play_btn = Gtk.Button(label="Play")
        self.play_btn.set_tooltip_text("Play / pause the take (Ctrl+P)")
        self.play_btn.add_css_class("pill")
        self.play_btn.set_sensitive(False)
        self.play_btn.connect("clicked", self._on_play_clicked)
        controls.append(self.play_btn)

        self.save_btn = Gtk.Button(label="Save WAV…")
        self.save_btn.add_css_class("pill")
        self.save_btn.set_sensitive(False)
        self.save_btn.connect("clicked", self._on_save_clicked)
        controls.append(self.save_btn)

        page.append(controls)

        # --- waveform ------------------------------------------------------- #
        wave_group = Adw.PreferencesGroup(
            title="Waveform",
            description="Click anywhere on the take to seek playback there.")
        self.waveform = Waveform(on_seek=self._on_seek)
        frame = Gtk.Frame()
        frame.set_child(self.waveform)
        frame.set_margin_top(6)
        frame.set_margin_bottom(6)
        frame.set_margin_start(12)
        frame.set_margin_end(12)
        wave_group.add(frame)
        page.append(wave_group)

        # --- verdict -------------------------------------------------------- #
        self.verdict_group = Adw.PreferencesGroup(title="Verdict")
        self.verdict_row = Adw.ActionRow(title="No take yet")
        self.verdict_row.set_subtitle("Record a few seconds of normal speech.")
        self.verdict_row.set_subtitle_lines(0)
        self.verdict_icon = Gtk.Image.new_from_icon_name(
            "audio-input-microphone-symbolic")
        self.verdict_row.add_prefix(self.verdict_icon)
        self.verdict_group.add(self.verdict_row)

        self.measure_rows: list[Adw.ActionRow] = []
        for label, _ in Analysis(np.zeros(0)).rows():
            row = Adw.ActionRow(title=label)
            row.add_suffix(self._mono_label("—", row))
            self.verdict_group.add(row)
            self.measure_rows.append(row)
        page.append(self.verdict_group)

        self.reload_devices()
        self._device_poll = GLib.timeout_add_seconds(
            3, self._poll_devices_tick)

        self.connect("close-request", self._on_close)

        Adw.StyleManager.get_default().connect(
            "notify::dark", lambda *_: (self.waveform.queue_draw(),
                                        self.meter.queue_draw()))

    # -- small helpers ------------------------------------------------------ #

    @staticmethod
    def _mono_label(text, row):
        lbl = Gtk.Label(label=text, xalign=1)
        lbl.add_css_class("numeric")
        lbl.add_css_class("dim-label")
        row._value_label = lbl
        return lbl

    def _set_record_idle(self):
        self.record_btn.set_label("Record")
        self.record_btn.remove_css_class("destructive-action")
        self.record_btn.add_css_class("suggested-action")

    def _set_record_active(self):
        self.record_btn.set_label("Stop")
        self.record_btn.remove_css_class("suggested-action")
        self.record_btn.add_css_class("destructive-action")

    def toast(self, text: str):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=4))

    def show_banner(self, text: str):
        self.banner.set_title(text)
        self.banner.set_revealed(True)

    def hide_banner(self):
        self.banner.set_revealed(False)

    # -- devices ------------------------------------------------------------ #

    def selected_device(self) -> Device | None:
        idx = self.device_row.get_selected()
        if 0 <= idx < len(self.devices):
            return self.devices[idx]
        return None

    def _resolve_preferred(self, devices: list[Device]) -> str | None:
        """--device may be a full source name or a description substring."""
        want = self.preferred_device
        if not want:
            return None
        for d in devices:
            if d.name == want:
                return d.name
        for d in devices:
            if want.lower() in d.description.lower():
                return d.name
        return None

    def reload_devices(self, announce: bool = False):
        keep = self.selected_device()
        keep_name = keep.name if keep else default_source()
        self.devices = list_devices()
        if keep is None:
            keep_name = self._resolve_preferred(self.devices) or keep_name

        # Rebuilding the model and reassigning the selection both emit
        # notify::selected; suppress the handler across the whole rebuild so it
        # cannot clear a banner this very call is about to raise.
        self._suppress_device_signal = True
        try:
            self.device_model.splice(0, self.device_model.get_n_items(),
                                     [d.label() for d in self.devices])

            if not self.devices:
                self.record_btn.set_sensitive(False)
                self.show_banner(
                    "No capture devices found. Is PipeWire running?")
                return

            self.record_btn.set_sensitive(True)
            target = next((i for i, d in enumerate(self.devices)
                           if d.name == keep_name), None)
            vanished = target is None
            if vanished:
                target = 0
            self.device_row.set_selected(target)
        finally:
            self._suppress_device_signal = False

        if vanished and keep is not None:
            self.show_banner(
                f"“{keep.description}” disappeared — switched to "
                f"“{self.devices[0].description}”.")
        elif not vanished:
            self.hide_banner()

        if announce:
            n = len(self.devices)
            self.toast(f"Found {n} capture device{'' if n == 1 else 's'}.")

    def _poll_devices_tick(self) -> bool:
        # Cheap liveness check: if the selected source vanished (USB mic pulled
        # while idle) rebuild the list so the dropdown never points at a ghost.
        current = self.selected_device()
        names = {d.name for d in list_devices()}
        if current is not None and current.name not in names:
            self.reload_devices()
        elif len(names) != len(self.devices):
            self.reload_devices()
        return True

    def _on_device_changed(self, *_):
        if getattr(self, "_suppress_device_signal", False):
            return
        if self.recorder is not None:
            self.recorder.stop()
        self.hide_banner()

    # -- record ------------------------------------------------------------- #

    def _on_record_clicked(self, *_):
        if self.recorder is not None:
            self.recorder.stop()
            return

        device = self.selected_device()
        if device is None:
            self.toast("No input device selected.")
            return

        self._stop_playback()
        self.samples = np.zeros(0, dtype=np.float32)
        self.analysis = None
        self.waveform.clear()
        self.meter.reset()
        self.play_btn.set_sensitive(False)
        self.save_btn.set_sensitive(False)
        self._reset_verdict("Recording…", "Speak normally for a few seconds.")
        self.hide_banner()

        self.recorder = Recorder(device.name,
                                 on_level=self._on_level,
                                 on_stop=self._on_capture_stopped)
        self.recorder.start()
        if self.recorder is None:      # start() may have failed synchronously
            return
        self._set_record_active()
        self.device_row.set_sensitive(False)
        self.waveform.set_envelope(self.recorder.envelope, live=True)
        self._rec_start = GLib.get_monotonic_time()
        self._rec_timer = GLib.timeout_add(80, self._tick_recording)

    def _tick_recording(self) -> bool:
        if self.recorder is None:
            self._rec_timer = None
            return False
        secs = (GLib.get_monotonic_time() - self._rec_start) / 1e6
        self.waveform.set_envelope(self.recorder.envelope, live=True)
        self.verdict_row.set_title(f"Recording… {secs:0.1f} s")
        self.verdict_row.set_subtitle(
            f"Stops automatically at {MAX_SECONDS} s.")
        return True

    def _on_level(self, rms_db, peak_db, _cols):
        self.meter.set_levels(rms_db, peak_db)
        self.level_label.set_text(
            f"RMS {rms_db:+.1f} dBFS   ·   peak {peak_db:+.1f} dBFS")

    def _on_capture_stopped(self, samples, envelope, error) -> bool:
        self.recorder = None
        if self._rec_timer is not None:
            GLib.source_remove(self._rec_timer)
            self._rec_timer = None
        self._set_record_idle()
        self.device_row.set_sensitive(True)
        self.samples = samples
        self.waveform.set_envelope(envelope, live=False)

        if error:
            kept = samples.size / float(RATE)
            if kept >= 0.25:
                self.show_banner(
                    f"Capture device failed mid-take ({error}) — kept the "
                    f"first {kept:.1f} s.")
            else:
                self.show_banner(f"Capture failed: {error}")
            self.reload_devices()

        if samples.size == 0:
            self._reset_verdict("Nothing captured",
                                error or "The device produced no audio.")
            self.meter.reset()
            self.level_label.set_text("Idle — no signal")
            return False

        self.analysis = Analysis(samples, RATE)
        write_wav(self.wav_path, samples, RATE)
        self.play_btn.set_sensitive(True)
        self.save_btn.set_sensitive(True)
        self._show_verdict(self.analysis)
        self.level_label.set_text(
            f"Take: {self.analysis.duration:.2f} s   ·   peak "
            f"{self.analysis.peak_db:+.1f} dBFS   ·   RMS "
            f"{self.analysis.rms_db:+.1f} dBFS")
        return False

    # -- verdict ------------------------------------------------------------ #

    def _reset_verdict(self, title, subtitle):
        self.verdict_row.set_title(title)
        self.verdict_row.set_subtitle(subtitle)
        for cls in ("success", "warning", "error"):
            self.verdict_row.remove_css_class(cls)
        for row in self.measure_rows:
            row._value_label.set_text("—")

    def _show_verdict(self, a: Analysis):
        icons = {"good": "emblem-ok-symbolic",
                 "warn": "dialog-warning-symbolic",
                 "bad": "dialog-error-symbolic"}
        classes = {"good": "success", "warn": "warning", "bad": "error"}
        for cls in ("success", "warning", "error"):
            self.verdict_row.remove_css_class(cls)
        self.verdict_row.add_css_class(classes[a.severity])
        self.verdict_icon.set_from_icon_name(icons[a.severity])
        self.verdict_row.set_title(a.verdict.capitalize())
        self.verdict_row.set_subtitle(a.detail)
        for row, (_label, value) in zip(self.measure_rows, a.rows()):
            row._value_label.set_text(value)

    # -- playback ----------------------------------------------------------- #

    def _ensure_player(self):
        if self.player is not None:
            return self.player
        self.player = Gst.ElementFactory.make("playbin", "player")
        bus = self.player.get_bus()
        bus.add_signal_watch()
        self._player_bus_id = bus.connect("message", self._on_player_message)
        return self.player

    def _on_play_clicked(self, *_):
        if self.player is not None:
            state = self.player.get_state(0).state
            if state == Gst.State.PLAYING:
                self.player.set_state(Gst.State.PAUSED)
                self.play_btn.set_label("Play")
                return
            if state == Gst.State.PAUSED:
                self.player.set_state(Gst.State.PLAYING)
                self.play_btn.set_label("Pause")
                self._start_position_timer()
                return
        self._start_playback(0.0)

    def _start_playback(self, fraction: float):
        if self.samples.size == 0:
            return
        player = self._ensure_player()
        player.set_state(Gst.State.NULL)
        player.set_property("uri", Gio.File.new_for_path(self.wav_path).get_uri())
        player.set_state(Gst.State.PLAYING)
        if fraction > 0:
            GLib.timeout_add(120, self._deferred_seek, fraction)
        self.play_btn.set_label("Pause")
        self._start_position_timer()

    def _deferred_seek(self, fraction) -> bool:
        if self.player is None:
            return False
        dur = self.samples.size / float(RATE)
        self.player.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            int(fraction * dur * Gst.SECOND))
        return False

    def _on_seek(self, fraction: float):
        self.waveform.set_cursor_fraction(fraction)
        if self.player is not None and \
                self.player.get_state(0).state in (Gst.State.PLAYING,
                                                   Gst.State.PAUSED):
            self._deferred_seek(fraction)
        else:
            self._start_playback(fraction)

    def _start_position_timer(self):
        if self._pos_timer is None:
            self._pos_timer = GLib.timeout_add(50, self._tick_position)

    def _tick_position(self) -> bool:
        if self.player is None:
            self._pos_timer = None
            return False
        ok, pos = self.player.query_position(Gst.Format.TIME)
        dur = self.samples.size / float(RATE)
        if ok and dur > 0:
            self.waveform.set_cursor_fraction(min(1.0, pos / Gst.SECOND / dur))
        return True

    def _on_player_message(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            self._stop_playback()
            self.waveform.set_cursor_fraction(None)
        elif message.type == Gst.MessageType.ERROR:
            err, _ = message.parse_error()
            self._stop_playback()
            self.toast(f"Playback failed: {err.message}")

    def _stop_playback(self):
        if self._pos_timer is not None:
            GLib.source_remove(self._pos_timer)
            self._pos_timer = None
        if self.player is not None:
            self.player.set_state(Gst.State.NULL)
        self.play_btn.set_label("Play")

    # -- save --------------------------------------------------------------- #

    def _on_save_clicked(self, *_):
        if self.samples.size == 0:
            return
        dialog = Gtk.FileDialog(initial_name="mic-fixer-take.wav")
        dialog.save(self, None, self._on_save_done)

    def _on_save_done(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        if gfile is None:
            return
        try:
            write_wav(gfile.get_path(), self.samples, RATE)
        except OSError as exc:
            self.toast(f"Could not save: {exc}")
            return
        self.toast(f"Saved {gfile.get_basename()}")

    # -- teardown ----------------------------------------------------------- #

    def _on_close(self, *_):
        if self.recorder is not None:
            self.recorder.stop()
        if self._device_poll is not None:
            GLib.source_remove(self._device_poll)
            self._device_poll = None
        self._stop_playback()
        if self.player is not None:
            bus = self.player.get_bus()
            if self._player_bus_id is not None:
                bus.disconnect(self._player_bus_id)
            bus.remove_signal_watch()
            self.player = None
        self._clean_scratch()
        return False

    def _clean_scratch(self):
        try:
            if os.path.exists(self.wav_path):
                os.unlink(self.wav_path)
            os.rmdir(self._scratch)
        except OSError:
            pass


class MicFixerApp(Adw.Application):
    def __init__(self, preferred_device: str | None = None):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.preferred_device = preferred_device
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        # Exported on the session bus by GApplication, so the transport is
        # reachable from a keybind, a script, or `gdbus call` as well as the
        # buttons.
        for name, handler, accels in (
            ("record", self._act_record, ["<Control>r"]),
            ("play", self._act_play, ["<Control>p"]),
            ("rescan", self._act_rescan, ["<Control>d", "F5"]),
            ("quit", self._act_quit, ["<Control>q"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
            self.set_accels_for_action(f"app.{name}", accels)

        # A plain `kill` should tear the pipelines down and drop the scratch
        # take, exactly like closing the window does.
        for sig in (signal.SIGTERM, signal.SIGINT):
            unix_signal_add(GLib.PRIORITY_DEFAULT, sig,
                            lambda: (self._act_quit(), False)[1])

    def do_activate(self):
        if self.window is None:
            self.window = MicFixerWindow(self, self.preferred_device)
        self.window.present()

    def _act_record(self, *_):
        if self.window:
            self.window._on_record_clicked()

    def _act_play(self, *_):
        if self.window and self.window.play_btn.get_sensitive():
            self.window._on_play_clicked()

    def _act_rescan(self, *_):
        if self.window:
            self.window.reload_devices(True)

    def _act_quit(self, *_):
        if self.window:
            self.window.close()
        self.quit()


# --------------------------------------------------------------------------- #
# Headless probe — same Recorder + Analysis the GUI uses
# --------------------------------------------------------------------------- #

def run_probe(device: str | None, seconds: float, as_json: bool,
              wav: str | None) -> int:
    devices = list_devices()
    if not devices:
        print("No capture devices found.", file=sys.stderr)
        return 1
    if device is None:
        want = default_source()
        match = next((d for d in devices if d.name == want), devices[0])
    else:
        match = next((d for d in devices
                      if d.name == device or device.lower()
                      in d.description.lower()), None)
        if match is None:
            print(f"No such capture source: {device}", file=sys.stderr)
            return 1

    loop = GLib.MainLoop()
    result: dict = {}

    def on_stop(samples, envelope, error):
        result["samples"] = samples
        result["error"] = error
        loop.quit()
        return False

    rec = Recorder(match.name, on_stop=on_stop,
                   max_seconds=max(1, int(math.ceil(seconds))))
    rec.start()
    GLib.timeout_add(int(seconds * 1000), lambda: (rec.stop(), False)[1])
    loop.run()

    samples = result.get("samples", np.zeros(0, dtype=np.float32))
    analysis = Analysis(samples, RATE)
    if wav and samples.size:
        write_wav(wav, samples, RATE)

    payload = analysis.as_dict()
    payload["device"] = match.name
    payload["device_description"] = match.description
    if result.get("error"):
        payload["capture_error"] = result["error"]
    if wav and samples.size:
        payload["wav"] = wav

    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"device   {match.description}")
        print(f"         {match.name}")
        for label, value in analysis.rows():
            print(f"{label:<22} {value}")
        print(f"verdict  {analysis.verdict.upper()}")
        print(f"         {analysis.detail}")
        if result.get("error"):
            print(f"note     capture ended early: {result['error']}")
        if wav and samples.size:
            print(f"wav      {wav}")
    return 0 if samples.size else 2


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mic-fixer", description="Native microphone checker (GTK4).")
    parser.add_argument("--list-devices", action="store_true",
                        help="print real capture sources and exit")
    parser.add_argument("--probe", action="store_true",
                        help="record headlessly and print the analysis")
    parser.add_argument("--device", metavar="NAME",
                        help="source name (or a substring of its description); "
                             "preselects the dropdown in GUI mode")
    parser.add_argument("--seconds", type=float, default=3.0,
                        help="probe length in seconds (default 3)")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable probe output")
    parser.add_argument("--wav", metavar="PATH",
                        help="write the probe capture to PATH")
    args = parser.parse_args(argv[1:])

    if "XDG_RUNTIME_DIR" not in os.environ and os.path.isdir(
            f"/run/user/{os.getuid()}"):
        os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"

    Gst.init(None)

    if args.list_devices:
        for d in list_devices():
            print(f"{d.name}\t{d.description}")
        return 0

    if args.probe:
        return run_probe(args.device, max(0.2, args.seconds), args.json,
                         args.wav)

    GLib.set_prgname("mic-fixer")
    GLib.set_application_name("Mic Fixer")
    Adw.init()
    return MicFixerApp(args.device).run([argv[0]])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
