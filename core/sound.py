"""
Pure-numpy sound synthesis for MemoryNest Sync.

No external audio assets — every sound is generated at runtime from numpy
oscillators and cached as 16-bit PCM WAV files in `assets/sounds/`.

Themes:
    nature   — chirp / leaf rustle / warble  (organic, calm)
    minimal  — click / chime / muted thud    (clean, subtle)
    none     — silence

Events:
    start, complete, error

Playback uses Windows `winsound.PlaySound(..., SND_ASYNC)` so the GUI
thread is never blocked. On non-Windows platforms `play()` is a no-op
(silent fallback).
"""

import logging
import threading
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44_100
THEMES = ("nature", "minimal", "none")
EVENTS = ("start", "complete", "error")


# ──────────────────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────────────────

class SoundEngine:
    """Caches synthesized WAVs on disk and plays them asynchronously."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._enabled = False
        self._theme   = "nature"
        self._volume  = 0.6
        self._render_all_missing()

    # ── public ────────────────────────────────────────────────────────────────

    def configure(self, *, enabled: bool, theme: str, volume: float) -> None:
        self._enabled = bool(enabled)
        self._theme   = theme if theme in THEMES else "none"
        self._volume  = max(0.0, min(1.0, float(volume)))

    def play(self, event: str) -> None:
        """Fire-and-forget. Safe to call from any thread."""
        if not self._enabled or self._theme == "none" or event not in EVENTS:
            return
        wav = self._cache_dir / f"{self._theme}_{event}.wav"
        if not wav.exists():
            return
        threading.Thread(target=self._play_async, args=(wav,), daemon=True).start()

    def preview(self, theme: str, event: str) -> None:
        """Test-button helper — plays even if globally disabled."""
        if theme == "none" or event not in EVENTS:
            return
        wav = self._cache_dir / f"{theme}_{event}.wav"
        if wav.exists():
            threading.Thread(target=self._play_async, args=(wav,), daemon=True).start()

    # ── private ───────────────────────────────────────────────────────────────

    def _play_async(self, wav_path: Path) -> None:
        try:
            import winsound
            flags = (winsound.SND_FILENAME
                     | winsound.SND_ASYNC
                     | winsound.SND_NODEFAULT)
            winsound.PlaySound(str(wav_path), flags)
        except Exception:
            logger.debug("Sound playback skipped (non-Windows or error)",
                         exc_info=True)

    def _render_all_missing(self) -> None:
        for theme in ("nature", "minimal"):
            for event in EVENTS:
                wav = self._cache_dir / f"{theme}_{event}.wav"
                if not wav.exists():
                    try:
                        samples = _render(theme, event)
                        _write_wav(wav, samples, self._volume)
                    except Exception:
                        logger.warning("Failed to render %s_%s", theme, event,
                                       exc_info=True)


# ──────────────────────────────────────────────────────────────────────────────
# WAV writer
# ──────────────────────────────────────────────────────────────────────────────

def _write_wav(path: Path, samples: np.ndarray, master_gain: float = 0.7) -> None:
    samples = np.clip(samples * master_gain, -1.0, 1.0)
    pcm = (samples * 32_767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())


# ──────────────────────────────────────────────────────────────────────────────
# Synth primitives
# ──────────────────────────────────────────────────────────────────────────────

def _envelope(n: int, attack_s: float, decay_s: float) -> np.ndarray:
    """Linear attack-sustain-decay envelope (sustain fills the middle)."""
    a = max(1, int(attack_s * SAMPLE_RATE))
    d = max(1, int(decay_s  * SAMPLE_RATE))
    s = max(0, n - a - d)
    parts = [np.linspace(0, 1, a),
             np.ones(s),
             np.linspace(1, 0, d)]
    env = np.concatenate(parts)[:n]
    if len(env) < n:
        env = np.concatenate([env, np.zeros(n - len(env))])
    return env


def _sine(freq: float, dur_s: float) -> np.ndarray:
    t = np.linspace(0, dur_s, int(SAMPLE_RATE * dur_s), endpoint=False)
    return np.sin(2 * np.pi * freq * t)


def _logchirp(f1: float, f2: float, dur_s: float) -> np.ndarray:
    """Logarithmic frequency sweep — sounds more natural for bird-like chirps."""
    t  = np.linspace(0, dur_s, int(SAMPLE_RATE * dur_s), endpoint=False)
    k  = np.log(f2 / f1) / dur_s
    phase = 2 * np.pi * f1 * (np.exp(k * t) - 1) / k
    return np.sin(phase)


def _noise(dur_s: float) -> np.ndarray:
    return np.random.uniform(-1.0, 1.0, int(SAMPLE_RATE * dur_s))


def _smooth(x: np.ndarray, win: int) -> np.ndarray:
    """Simple moving-average lowpass — colours noise into 'rustle'."""
    if win <= 1:
        return x
    return np.convolve(x, np.ones(win) / win, mode="same")


# ──────────────────────────────────────────────────────────────────────────────
# Render dispatch
# ──────────────────────────────────────────────────────────────────────────────

def _render(theme: str, event: str) -> np.ndarray:
    return {
        ("nature",  "start"):    _nature_start,
        ("nature",  "complete"): _nature_complete,
        ("nature",  "error"):    _nature_error,
        ("minimal", "start"):    _minimal_start,
        ("minimal", "complete"): _minimal_complete,
        ("minimal", "error"):    _minimal_error,
    }[(theme, event)]()


# ── Nature theme — bird/breeze inspired ───────────────────────────────────────

def _nature_start() -> np.ndarray:
    """Cheerful 3-note ascending bird tweet — 'let's begin!'

    Designed to feel uplifting and inviting without overlapping the
    completion sound's character. Three short rising chirps in a major-
    third progression (1700 → 2200 → 2700 Hz), each with its own micro
    upward sweep so it sounds organic, not synthetic.
    """
    notes = [
        (1700, 1900, 0.08),   # low chirp
        (2200, 2450, 0.07),   # mid chirp
        (2700, 3050, 0.10),   # bright top chirp (slightly longer)
    ]
    parts = []
    gap = np.zeros(int(SAMPLE_RATE * 0.025))
    for i, (f1, f2, dur) in enumerate(notes):
        c = _logchirp(f1, f2, dur)
        c *= _envelope(len(c), 0.004, dur - 0.005)
        parts.append(c)
        if i < len(notes) - 1:
            parts.append(gap)
    return np.concatenate(parts) * 0.5


def _nature_complete() -> np.ndarray:
    """Two-note bird song — descending then resting (a 'finished' feel).

    Differs from start in shape: longer notes, downward inflection on the
    second one, more sustained — 'done, all settled' rather than 'go!'.
    """
    # first note: gentle rising sweep
    c1 = _logchirp(2400, 2900, 0.16)
    c1 *= _envelope(len(c1), 0.006, 0.15)
    gap = np.zeros(int(SAMPLE_RATE * 0.06))
    # second note: descending sweep — resolves the phrase
    c2 = _logchirp(2700, 2200, 0.20)
    c2 *= _envelope(len(c2), 0.006, 0.19)
    return np.concatenate([c1, gap, c2]) * 0.55


def _nature_error() -> np.ndarray:
    """Gentle descending warble — soft 'aww' tone with vibrato."""
    dur = 0.42
    t   = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    base    = 290 - 90 * (t / dur)               # 290 → 200 Hz
    vibrato = 6 * np.sin(2 * np.pi * 5.5 * t)
    phase   = 2 * np.pi * np.cumsum(base + vibrato) / SAMPLE_RATE
    fund    = np.sin(phase)
    octave  = 0.35 * np.sin(2 * phase)           # body / warmth
    sig     = 0.75 * fund + octave
    env     = _envelope(len(sig), 0.03, 0.36)
    return sig * env * 0.45


# ── Minimal theme — clean, percussive ─────────────────────────────────────────

def _minimal_start() -> np.ndarray:
    """Soft click — quick blip."""
    s = _sine(800, 0.06)
    s *= _envelope(len(s), 0.002, 0.055)
    return s * 0.55


def _minimal_complete() -> np.ndarray:
    """Two-note ascending chime — A5 → E6 (perfect fifth)."""
    n1 = _sine(880.0,   0.18)
    n2 = _sine(1_318.5, 0.18)
    env = _envelope(len(n1), 0.005, 0.17)
    return np.concatenate([n1 * env, n2 * env]) * 0.5


def _minimal_error() -> np.ndarray:
    """Low muted thud."""
    s = _sine(180, 0.20)
    s *= _envelope(len(s), 0.005, 0.19)
    return s * 0.6
