"""An original classical-style soundtrack for the Haggle video, for solo piano and harp.

uv run --python 3.12 --no-project --with numpy python music_classical.py   ->  bgm_classical.wav

Everything is generated with numpy, so there is nothing to license. The harmony follows the
picture: a calm C major opening, an A minor allegro for the fight, rising harp runs into a big
C major arrival at "Deal", a lyrical section for the Shield, and a final cadence. 120 BPM, 22 bars
of 2s each. The piano sings the tune and holds the bass; the harp plays the arpeggios and glissandi.
(The earlier strings version lives in music_classical_strings.py.)
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


def harp(m: float, ring: float = 1.6, vel: float = 1.0) -> np.ndarray:
    """A plucked string: bright attack, upper partials dying faster, a soft finger click."""
    t = tgrid(ring)
    f = mtof(m)
    base = 3.6 / ring
    out = np.zeros_like(t)
    for h in range(1, 11):
        out += np.sin(2 * np.pi * f * h * t) / h**1.3 * np.exp(-t * (base + 0.5 * h + max(0.0, m - 60) * 0.018))
    pluck = rng.standard_normal(len(t)) * np.exp(-t * 260) * 0.035
    return (out + pluck) * np.minimum(1, t * 1100) * np.clip((ring - t) / 0.25, 0, 1) * vel


def glissando(b: np.ndarray, start: float, notes: list[int], span: float, gain: float, ring: float = 1.8, pan: float = 0.25) -> None:
    for k, m in enumerate(notes):
        put(b, start + span * k / len(notes), harp(m, ring), gain=gain * (0.75 + 0.25 * k / len(notes)), pan=pan)


# ---- harmony and tune ---------------------------------------------------------------------------

# name -> (triad for the arpeggios, bass root for the piano's left hand)
CHORDS = {
    "C": ([60, 64, 67], 36),
    "G": ([55, 59, 62], 31),
    "Am": ([57, 60, 64], 33),
    "F": ([53, 57, 60], 29),
    "Dm": ([62, 65, 69], 38),
    "E": ([56, 59, 64], 28),
    "G7": ([55, 59, 62], 31),
}
PROG = ["C", "G", "Am", "F", "C", "G", "Am", "Dm", "E", "Am", "F", "G", "E", "C", "F", "G", "Am", "Dm", "G7", "C", "C", "C"]
BARS = len(PROG)

# Piano melody per bar: (beat, midi, length in beats).
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

piano_bus, harp_bus, sfx_bus = bus(), bus(), bus()
ORDER = [0, 1, 2, 3, 4, 3, 2, 1]

for bar in range(BARS):
    t0 = bar * BAR
    triad, root = CHORDS[PROG[bar]]
    arp = triad + [triad[0] + 12, triad[1] + 12]

    # Harp arpeggios: gentle eighths, running sixteenths in the fight, eighths again for the Shield.
    if bar <= 5 or 14 <= bar <= 17:
        gain = 0.1 + 0.012 * min(bar, 5) if bar <= 5 else 0.15
        for i in range(8):
            put(harp_bus, t0 + i * BEAT / 2, harp(arp[ORDER[i]], 1.5), gain=gain * (1.1 if i % 4 == 0 else 1.0) * (1.7 if bar < 2 else 1.0), pan=0.3)
    elif 6 <= bar <= 13:
        for i in range(16):
            put(harp_bus, t0 + i * BEAT / 4, harp(arp[ORDER[i % 8]], 1.0), gain=0.15 * (1.25 if i % 4 == 0 else 1.0), pan=0.3)
    elif bar in (18, 19):
        for k, m in enumerate([triad[0] - 12, triad[1] - 12, triad[2] - 12] + triad):
            put(harp_bus, t0 + k * 0.07, harp(m, 2.6), gain=0.17, pan=0.25)
    elif bar == 20:
        for k, m in enumerate([48, 55, 60, 64, 67, 72, 76]):
            put(harp_bus, t0 + k * 0.16, harp(m, 3.2), gain=0.15, pan=0.25)

    # Piano left hand: a long root, with a drive on beats 1 and 3 in the fight.
    if 2 <= bar <= 19:
        put(piano_bus, t0, piano(root, BAR * 0.97), gain=0.24, pan=-0.2)
        put(piano_bus, t0, piano(root + 7, BAR * 0.97), gain=0.1, pan=-0.2)
        if 6 <= bar <= 13:
            put(piano_bus, t0 + 2 * BEAT, piano(root + 12, BEAT * 1.8), gain=0.14, pan=-0.2)
    elif bar < 2:
        put(piano_bus, t0, piano(root + 12, BAR), gain=0.22, pan=-0.2)

    # Piano melody.
    for beat_pos, m, beats in MELODY.get(bar, []):
        put(piano_bus, t0 + beat_pos * BEAT, piano(m, beats * BEAT * 0.97), gain=0.23 if bar < 20 else 0.18, pan=0.0)

    if bar in (19, 20):
        for k, m in enumerate([48, 55, 60, 64]):
            put(piano_bus, t0 + k * 0.03, piano(m, BAR * 1.2), gain=0.14, pan=-0.1)

# The run into the deal: four rising harp arpeggios on E, growing in force, then a big C major arrival.
E_RUN = [40, 47, 52, 56, 59, 64, 68, 71, 76, 80, 83, 88]
C_SCALE = [48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83, 84, 86, 88]
deal = TL["deal"]
for k in range(4):
    glissando(harp_bus, deal - 1.95 + k * 0.5, E_RUN, 0.42, gain=0.1 + 0.06 * k, ring=1.1)
for k, m in enumerate([24, 36, 43, 48, 52, 55, 60, 64, 67, 72]):
    put(piano_bus, deal + k * 0.012, piano(m, BAR * 1.4), gain=0.26, pan=-0.05)
glissando(harp_bus, deal, C_SCALE, 0.85, gain=0.2, ring=2.2)
# The close: a rising glissando on the last tonic chord.
glissando(harp_bus, 19 * BAR + 0.05, C_SCALE, 1.0, gain=0.17, ring=2.6)

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
    put(sfx_bus, deal + 0.05 + k * 0.09, bell(m, 2.0), gain=0.11)
for k, m in enumerate((79, 84, 88, 91)):
    put(sfx_bus, TL["state_times"]["paid"] + k * 0.1, bell(m, 2.2), gain=0.13)

# ---- mix --------------------------------------------------------------------------------------

hall = np.stack([reverb(harp_bus[c] * 0.9 + piano_bus[c] * 0.7 + sfx_bus[c] * 0.4) for c in range(2)])
mix = piano_bus + harp_bus + sfx_bus + hall * 0.4
mix = np.stack([fft_filter(mix[c], low=14000, high=30) for c in range(2)])

tt = np.arange(N) / SR
mix *= np.clip(tt / 1.0, 0, 1) * np.clip((DUR + 0.6 - tt) / 2.4, 0, 1)
mix = mix[:, : int(DUR * SR)]
body = mix[:, int(6 * SR): int(24 * SR)]
mix *= 0.14 / np.sqrt((body**2).mean())  # body of the piece near -17 dBFS RMS
mix = np.tanh(mix * 1.1) / 1.1  # gently tame the 'Deal' chord instead of letting it set the level
mix *= 0.89 / np.abs(mix).max()

pcm = (mix.T * 32767).astype("<i2")
with wave.open("bgm_classical.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f"bgm_classical.wav: {mix.shape[1] / SR:.2f}s, {BPM} BPM, {BARS} bars, piano and harp")
