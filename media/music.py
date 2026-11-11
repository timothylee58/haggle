"""Synthesises the lofi soundtrack and UI sounds for the Haggle video.

uv run --no-project --with numpy python music.py   ->  bgm.wav

Everything is generated from scratch (FM electric piano, sine bass, synthetic drums, vinyl
crackle), so there is nothing to license. Sound effects land on the same timeline.json that the
video uses, so clicks, message pops and chimes line up with the picture.
"""

import json
import wave

import numpy as np

SR = 44100
TL = json.load(open("timeline.json"))
DUR, BPM = TL["duration"], TL["bpm"]
BEAT = 60 / BPM
N = int((DUR + 1.2) * SR)
rng = np.random.default_rng(7)


def mtof(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def bus() -> np.ndarray:
    return np.zeros((2, N))


def put(b: np.ndarray, start: float, sig: np.ndarray, gain: float = 1.0, pan: float = 0.0) -> None:
    i = int(start * SR)
    if i >= N or i < 0:
        return
    j = min(N, i + len(sig))
    s = sig[: j - i] * gain
    angle = (pan + 1) * np.pi / 4
    b[0, i:j] += s * np.cos(angle)
    b[1, i:j] += s * np.sin(angle)


def tgrid(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def fft_filter(x: np.ndarray, low: float | None = None, high: float | None = None) -> np.ndarray:
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    if low:
        spec *= 1 / np.sqrt(1 + (f / low) ** 6)
    if high:
        spec *= 1 - 1 / np.sqrt(1 + (f / high) ** 4)
    return np.fft.irfft(spec, len(x))


def reverb(x: np.ndarray, seconds: float = 1.5, decay: float = 3.0) -> np.ndarray:
    t = tgrid(seconds)
    ir = rng.standard_normal(len(t)) * np.exp(-t * decay)
    ir = fft_filter(ir, low=3500)
    ir /= np.abs(ir).sum() / 8
    n = 1 << int(np.ceil(np.log2(len(x) + len(ir))))
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[: len(x)]


# ---- instruments ------------------------------------------------------------------------------


def ep(m: float, length: float, vel: float = 1.0) -> np.ndarray:
    t = tgrid(length + 0.7)
    f = mtof(m)
    attack = np.minimum(1, t * 350)
    release = np.clip((length + 0.45 - t) / 0.45, 0, 1)
    env = np.exp(-t * (1.9 + (m - 55) * 0.018)) * attack * release
    index = 1.15 * np.exp(-t * 3.2) + 0.12
    body = np.sin(2 * np.pi * f * t + index * np.sin(2 * np.pi * f * t))
    tine = 0.16 * np.exp(-t * 16) * np.sin(2 * np.pi * f * 7 * t)
    return (body + tine) * env * (1 + 0.07 * np.sin(2 * np.pi * 4.6 * t)) * vel


def bass(m: float, length: float) -> np.ndarray:
    t = tgrid(length + 0.25)
    f = mtof(m)
    env = np.minimum(1, t * 250) * np.clip((length + 0.15 - t) / 0.15, 0, 1) * np.exp(-t * 1.6)
    return (np.sin(2 * np.pi * f * t) + 0.28 * np.sin(4 * np.pi * f * t)) * env


def pluck(m: float) -> np.ndarray:
    t = tgrid(1.2)
    f = mtof(m)
    env = np.exp(-t * 5.5) * np.minimum(1, t * 600)
    return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)) * env


def kick() -> np.ndarray:
    t = tgrid(0.42)
    phase = 2 * np.pi * (46 * t + 95 * (1 - np.exp(-34 * t)) / 34)
    click = rng.standard_normal(len(t)) * np.exp(-t * 500) * 0.25
    return np.sin(phase) * np.exp(-t * 8.5) + click


def snare() -> np.ndarray:
    t = tgrid(0.28)
    noise = rng.standard_normal(len(t))
    noise = noise - np.convolve(noise, np.ones(6) / 6, mode="same")
    return noise * np.exp(-t * 24) * 0.8 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 32) * 0.45


def hat(open_: bool = False) -> np.ndarray:
    t = tgrid(0.3 if open_ else 0.07)
    noise = rng.standard_normal(len(t))
    noise = noise - np.convolve(noise, np.ones(4) / 4, mode="same")
    return noise * np.exp(-t * (13 if open_ else 70))


# ---- arrangement ------------------------------------------------------------------------------

# One chord per bar: (rootless EP voicing, bass root). Cmaj7 / Am7 / Dm7 / G7, then Fmaj7 / Em7 / Dm7 / G7.
A = [([52, 55, 59, 62], 36), ([55, 57, 60, 64], 33), ([53, 57, 60, 64], 38), ([53, 55, 59, 62], 31)]
B = [([52, 57, 60, 65], 29), ([55, 59, 62, 64], 28), ([53, 57, 60, 64], 38), ([53, 55, 59, 62], 31)]
PROG = A + A + A + A + B + A[:2]
BARS = len(PROG)
GROOVE = (2, 17)  # kick, snare, bass
SHAKER = (5, 17)

# Bell motif, in beats from the start of a two-bar phrase.
MOTIF = [(0.0, 76), (0.5, 79), (1.5, 81), (2.0, 79), (3.5, 76), (4.0, 74), (5.0, 76), (6.0, 72), (6.75, 74)]

ep_bus, bass_bus, drum_bus, lead_bus, sfx_bus = bus(), bus(), bus(), bus(), bus()

for bar in range(BARS):
    t0 = bar * 4 * BEAT
    voicing, root = PROG[bar]
    # Electric piano comping with a lazy strum.
    for beat_pos, length in [(0.0, 1.4), (1.5, 0.45), (2.5, 0.45), (3.25, 0.6)]:
        if bar == BARS - 1 and beat_pos > 0:
            continue
        for k, m in enumerate(voicing):
            put(ep_bus, t0 + beat_pos * BEAT + k * 0.011, ep(m, length * BEAT), gain=0.2 * rng.uniform(0.85, 1.0), pan=-0.25 + 0.17 * k)
    if GROOVE[0] <= bar <= GROOVE[1]:
        for beat_pos, length in [(0.0, 1.4), (2.5, 0.4), (3.0, 0.9)]:
            put(bass_bus, t0 + beat_pos * BEAT, bass(root, length * BEAT), gain=0.42)
    if GROOVE[0] <= bar <= GROOVE[1]:
        for sixteenth in (0, 7, 10):
            put(drum_bus, t0 + sixteenth * BEAT / 4, kick(), gain=0.8 if sixteenth == 0 else 0.55)
        for sixteenth in (4, 12):
            put(drum_bus, t0 + sixteenth * BEAT / 4, snare(), gain=0.34)
    if bar >= 1:
        for eighth in range(8):
            swing = 0.07 * BEAT if eighth % 2 else 0.0
            vel = (0.16 if eighth % 2 == 0 else 0.1) * rng.uniform(0.8, 1.1)
            put(drum_bus, t0 + eighth * BEAT / 2 + swing, hat(), gain=vel, pan=0.3)
        if GROOVE[0] <= bar <= GROOVE[1]:
            put(drum_bus, t0 + 14 * BEAT / 4, hat(open_=True), gain=0.1, pan=0.3)
    if SHAKER[0] <= bar <= SHAKER[1]:
        for sixteenth in range(16):
            if sixteenth % 2:
                put(drum_bus, t0 + sixteenth * BEAT / 4, hat(), gain=0.045 * rng.uniform(0.6, 1.2), pan=-0.3)

# Bell lead from 12s, in two-bar phrases, with a soft echo.
for phrase_start in range(6, 18, 2):
    for beat_pos, m in MOTIF:
        start = (phrase_start * 4 + beat_pos) * BEAT
        note = pluck(m)
        put(lead_bus, start, note, gain=0.14, pan=0.2)
        put(lead_bus, start + 0.75 * BEAT, note, gain=0.05, pan=-0.35)

# ---- sound effects on the video timeline ---------------------------------------------------------


def click() -> np.ndarray:
    t = tgrid(0.05)
    n = rng.standard_normal(len(t))
    n = n - np.convolve(n, np.ones(5) / 5, mode="same")
    return n * np.exp(-t * 170) * 0.5 + np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 130) * 0.35


def pop(pitch: float) -> np.ndarray:
    t = tgrid(0.16)
    f = pitch * (1 + 0.5 * np.exp(-t * 40))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 26)


def bell(m: float, length: float = 1.6) -> np.ndarray:
    t = tgrid(length)
    f = mtof(m)
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 4) + 0.2 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 9)) * np.exp(-t * 3.2)


for c in TL["clicks"]:
    put(sfx_bus, c, click(), gain=0.5)
for i in range(10):
    put(sfx_bus, TL["match_start"] + i * TL["turn_gap"], pop(560 if i % 2 == 0 else 760), gain=0.16, pan=-0.3 if i % 2 == 0 else 0.3)
for key in ("held", "shipped", "delivered"):
    put(sfx_bus, TL["state_times"][key], bell(88, 0.7), gain=0.1)
for k, m in enumerate((84, 88, 91, 96)):
    put(sfx_bus, TL["deal"] + k * 0.09, bell(m, 2.0), gain=0.16)
for k, m in enumerate((79, 84, 88, 91)):
    put(sfx_bus, TL["state_times"]["paid"] + k * 0.1, bell(m, 2.2), gain=0.16)

# ---- mix ----------------------------------------------------------------------------------------

wet = np.stack([reverb(ep_bus[c] + lead_bus[c] * 0.8 + sfx_bus[c] * 0.5) for c in range(2)])
mix = ep_bus + bass_bus + drum_bus + lead_bus + sfx_bus + wet * 0.3

# Tape wobble: a slow, tiny pitch drift.
tt = np.arange(N) / SR
warp = tt + 0.0013 * np.sin(2 * np.pi * 0.55 * tt) + 0.0004 * np.sin(2 * np.pi * 3.1 * tt)
mix = np.stack([np.interp(warp, tt, mix[c]) for c in range(2)])

# Vinyl crackle and hiss.
crackle = np.zeros(N)
for pos in rng.integers(0, N - 400, int(DUR * 22)):
    length = int(rng.integers(20, 250))
    crackle[pos : pos + length] += rng.standard_normal(length) * np.exp(-np.arange(length) / (length / 4)) * rng.uniform(0.01, 0.05)
hiss = rng.standard_normal(N) * 0.0016
mix += (crackle + hiss) * np.array([[1.0], [0.9]])

# Dusty top end, warm saturation, then a gentle low cut.
mix = np.stack([fft_filter(mix[c], low=6200, high=28) for c in range(2)])
mix = np.tanh(mix * 1.25) / 1.25

fade_in = np.clip(tt / 0.8, 0, 1)
fade_out = np.clip((DUR + 0.6 - tt) / 2.2, 0, 1)
mix *= fade_in * fade_out
mix = mix[:, : int(DUR * SR)]
mix *= 0.89 / np.abs(mix).max()

pcm = (mix.T * 32767).astype("<i2")
with wave.open("bgm.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f"bgm.wav: {mix.shape[1] / SR:.2f}s, {BPM} BPM, {BARS} bars")
