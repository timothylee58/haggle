"""An original classical-style soundtrack for the Haggle video, synthesised from scratch.

uv run --python 3.12 --no-project --with numpy python music_classical.py   ->  bgm_classical_strings.wav

Strings, piano, solo violin and timpani, all generated with numpy. The harmony follows the picture:
a calm C major opening, an A minor allegro for the fight, a timpani roll into C major at "Deal",
a lyrical section for the Shield, and a final cadence. 120 BPM, 22 bars of 2s each.
"""

import json
import wave

import numpy as np

SR = 44100
TL = json.load(open("timeline.json"))
DUR = TL["duration"]
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT
N = int((DUR + 1.5) * SR)
rng = np.random.default_rng(11)


def mtof(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def bus() -> np.ndarray:
    return np.zeros((2, N))


def put(b: np.ndarray, start: float, sig: np.ndarray, gain: float = 1.0, pan: float = 0.0) -> None:
    i = int(start * SR)
    if i >= N or i < 0:
        return
    j = min(N, i + len(sig))
    angle = (pan + 1) * np.pi / 4
    b[0, i:j] += sig[: j - i] * gain * np.cos(angle)
    b[1, i:j] += sig[: j - i] * gain * np.sin(angle)


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


def reverb(x: np.ndarray, seconds: float = 2.6, decay: float = 1.7) -> np.ndarray:
    t = tgrid(seconds)
    ir = rng.standard_normal(len(t)) * np.exp(-t * decay)
    ir = fft_filter(ir, low=5000)
    ir /= np.abs(ir).sum() / 7
    n = 1 << int(np.ceil(np.log2(len(x) + len(ir))))
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[: len(x)]


# ---- instruments ------------------------------------------------------------------------------


def piano(m: float, length: float, vel: float = 1.0) -> np.ndarray:
    t = tgrid(length + 1.8)
    f = mtof(m)
    out = np.zeros_like(t)
    for h in range(1, 9):
        fh = f * h * np.sqrt(1 + 0.00025 * h * h)
        out += np.sin(2 * np.pi * fh * t) / h**1.15 * np.exp(-t * (1.3 + 0.8 * h + (m - 48) * 0.012))
    hammer = rng.standard_normal(len(t)) * np.exp(-t * 160) * 0.05
    release = np.clip((length + 0.35 - t) / 0.35, 0, 1) if length < 1.0 else np.clip((length + 1.2 - t) / 1.2, 0, 1)
    return (out + hammer) * np.minimum(1, t * 700) * release * vel


def bowed(m: float, length: float, vel: float = 1.0, attack: float = 0.3, voices=(-0.07, 0.0, 0.07), vib: float = 0.0035, harmonics: int = 10) -> np.ndarray:
    """A bowed string: detuned sawtooth-like voices with a slow attack and gentle vibrato."""
    t = tgrid(length + 0.9)
    f = mtof(m)
    sig = np.zeros_like(t)
    rate = 5.3
    for k, det in enumerate(voices):
        fk = f * 2 ** (det / 12)
        phase = 2 * np.pi * fk * t + (fk * vib / rate) * np.sin(2 * np.pi * rate * t + k) * np.minimum(1, t / 0.6)
        for h in range(1, harmonics + 1):
            sig += np.sin(h * phase) / h**1.25
    env = (1 - np.exp(-t / attack * 3)) * np.clip((length + 0.8 - t) / 0.8, 0, 1)
    return sig * env * vel / len(voices)


def timpani(f0: float, length: float = 1.8) -> np.ndarray:
    t = tgrid(length)
    f = f0 * (1 + 0.32 * np.exp(-t * 28))
    phase = 2 * np.pi * np.cumsum(f) / SR
    thump = rng.standard_normal(len(t)) * np.exp(-t * 90) * 0.18
    return (np.sin(phase) + 0.35 * np.sin(2 * phase)) * np.exp(-t * 2.6) + thump


# ---- harmony and tune ---------------------------------------------------------------------------

# (name, piano triad, cello root, string pad). One chord per 2-second bar.
CHORDS = {
    "C": ([60, 64, 67], 48, [55, 60, 64, 67]),
    "G": ([55, 59, 62], 43, [55, 59, 62, 67]),
    "Am": ([57, 60, 64], 45, [57, 60, 64, 69]),
    "F": ([53, 57, 60], 41, [53, 57, 60, 65]),
    "Dm": ([62, 65, 69], 50, [57, 62, 65, 69]),
    "E": ([56, 59, 64], 40, [52, 56, 59, 64]),
    "G7": ([55, 59, 62], 43, [53, 55, 59, 62]),
}
PROG = ["C", "G", "Am", "F", "C", "G", "Am", "Dm", "E", "Am", "F", "G", "E", "C", "F", "G", "Am", "Dm", "G7", "C", "C", "C"]
BARS = len(PROG)

# Violin melody per bar: (beat, midi, length in beats).
MELODY = {
    2: [(0, 76, 2), (2, 72, 1), (3, 74, 1)],
    3: [(0, 77, 2), (2, 76, 1), (3, 74, 1)],
    4: [(0, 72, 2), (2, 76, 1), (3, 79, 1)],
    5: [(0, 79, 2), (2, 77, 1), (3, 74, 1)],
    6: [(0, 76, 1), (1, 76, 0.5), (1.5, 77, 0.5), (2, 76, 1), (3, 72, 1)],
    7: [(0, 74, 1), (1, 74, 0.5), (1.5, 76, 0.5), (2, 77, 1), (3, 74, 1)],
    8: [(0, 76, 1), (1, 76, 0.5), (1.5, 74, 0.5), (2, 71, 1), (3, 68, 1)],
    9: [(0, 72, 1), (1, 76, 1), (2, 81, 2)],
    10: [(0, 81, 1), (1, 77, 1), (2, 77, 1), (3, 76, 1)],
    11: [(0, 74, 1), (1, 79, 1), (2, 77, 1), (3, 74, 1)],
    12: [(0, 80, 1), (1, 76, 1), (2, 74, 1), (3, 71, 1)],
    13: [(0, 79, 2), (2, 76, 1), (3, 72, 1)],
    14: [(0, 77, 2), (2, 81, 1), (3, 77, 1)],
    15: [(0, 79, 2), (2, 74, 1), (3, 71, 1)],
    16: [(0, 76, 2), (2, 72, 1), (3, 69, 1)],
    17: [(0, 74, 2), (2, 77, 1), (3, 81, 1)],
    18: [(0, 79, 2), (2, 77, 1), (3, 74, 1)],
    19: [(0, 72, 4)],
    20: [(0, 72, 8)],
}

strings_bus, violin_bus, piano_bus, cello_bus, timp_bus, sfx_bus = (bus() for _ in range(6))

for bar in range(BARS):
    t0 = bar * BAR
    piano_triad, root, pad = CHORDS[PROG[bar]]

    # String pad, swelling with the story.
    level = 1.2 if bar < 2 else 0.95 if bar < 6 else 0.85 if bar <= 13 else 0.8 if bar >= 18 else 0.75
    length = BAR * (4 if bar >= 19 else 1)
    if bar in (20, 21):
        continue_pad = False
    else:
        continue_pad = True
    if continue_pad:
        for k, m in enumerate(pad):
            put(strings_bus, t0, bowed(m, length + 0.15), gain=0.13 * level, pan=-0.4 + 0.27 * k)

    # Cello roots from the first violin entry.
    if 2 <= bar <= 19:
        put(cello_bus, t0, bowed(root, BAR * 0.97, attack=0.12, voices=(0.0, 0.05), harmonics=8), gain=0.2)
        if 6 <= bar <= 13:
            put(cello_bus, t0 + BAR / 2, bowed(root, BEAT * 1.9, attack=0.1, voices=(0.0, 0.05), harmonics=8), gain=0.14)

    # Piano: gentle eighths, running sixteenths in the fight, eighths again for the Shield, then chords.
    arp_up = piano_triad + [piano_triad[0] + 12, piano_triad[1] + 12]
    order = [0, 1, 2, 3, 4, 3, 2, 1]
    if 2 <= bar <= 5 or 14 <= bar <= 17:
        for i in range(8):
            put(piano_bus, t0 + i * BEAT / 2, piano(arp_up[order[i]], BEAT / 2, 1.0), gain=0.17 + 0.02 * (i % 2 == 0), pan=-0.15)
    elif 6 <= bar <= 13:
        for i in range(16):
            put(piano_bus, t0 + i * BEAT / 4, piano(arp_up[order[i % 8]], BEAT / 4, 1.0), gain=0.15 + 0.035 * (i % 4 == 0), pan=-0.15)
    elif bar in (18, 19):
        for k, m in enumerate(piano_triad + [piano_triad[0] + 12]):
            put(piano_bus, t0 + k * 0.025, piano(m, BAR * 1.6, 1.0), gain=0.24, pan=-0.1)
    elif bar == 20:
        for k, m in enumerate([48, 55, 60, 64, 67, 72]):
            put(piano_bus, t0 + k * 0.04, piano(m, BAR * 2.5, 1.0), gain=0.2, pan=-0.1)

    # Solo violin.
    for beat_pos, m, beats in MELODY.get(bar, []):
        put(violin_bus, t0 + beat_pos * BEAT, bowed(m, beats * BEAT * 0.97, attack=0.07, voices=(-0.04, 0.04), vib=0.006, harmonics=9), gain=0.2, pan=0.2)

# Timpani: a soft entry at the fight, a crescendo roll into the deal, and the final cadence.
put(timp_bus, 6 * BAR, timpani(110.0), gain=0.35)
roll_start, deal = TL["deal"] - 1.9, TL["deal"]
hits = np.arange(roll_start, deal, 0.125)
for k, h in enumerate(hits):
    put(timp_bus, h, timpani(82.4, 0.6), gain=0.12 + 0.34 * (k / len(hits)) ** 1.5)
put(timp_bus, deal, timpani(65.4, 2.6), gain=0.6)
put(timp_bus, deal, timpani(98.0, 2.6), gain=0.3)
put(timp_bus, 19 * BAR, timpani(65.4, 2.6), gain=0.5)

# ---- picture-synced sound effects, kept soft under the music ----------------------------------------


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
    put(sfx_bus, c, click(), gain=0.3)
for i in range(10):
    put(sfx_bus, TL["match_start"] + i * TL["turn_gap"], pop(660 if i % 2 == 0 else 880), gain=0.07, pan=-0.3 if i % 2 == 0 else 0.3)
for key in ("held", "shipped", "delivered"):
    put(sfx_bus, TL["state_times"][key], bell(88, 0.7), gain=0.08)
for k, m in enumerate((84, 88, 91, 96)):
    put(sfx_bus, deal + 0.05 + k * 0.09, bell(m, 2.0), gain=0.13)
for k, m in enumerate((79, 84, 88, 91)):
    put(sfx_bus, TL["state_times"]["paid"] + k * 0.1, bell(m, 2.2), gain=0.13)

# ---- mix --------------------------------------------------------------------------------------

hall = np.stack([reverb(strings_bus[c] * 0.9 + violin_bus[c] + piano_bus[c] * 0.55 + sfx_bus[c] * 0.4) for c in range(2)])
mix = strings_bus + violin_bus + piano_bus + cello_bus + timp_bus + sfx_bus + hall * 0.42
mix = np.stack([fft_filter(mix[c], low=14000, high=30) for c in range(2)])

tt = np.arange(N) / SR
mix *= np.clip(tt / 1.2, 0, 1) * np.clip((DUR + 0.6 - tt) / 2.4, 0, 1)
mix = mix[:, : int(DUR * SR)]
mix *= 0.89 / np.abs(mix).max()

pcm = (mix.T * 32767).astype("<i2")
with wave.open("bgm_classical_strings.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f"bgm_classical_strings.wav: {mix.shape[1] / SR:.2f}s, {BPM} BPM, {BARS} bars")
