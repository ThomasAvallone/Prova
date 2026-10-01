#!/usr/bin/env python3
"""Synthesises the soundtrack (music bed + sound effects) for the intro.

Every sound is placed from build/cues.json, which index.html exports, so audio and
animation always share the same timing.   usage: python3 audio.py build/cues.json build/audio.wav
"""
import json
import sys
import wave

import numpy as np
from scipy import signal

SR = 48000
BPM = 120
BEAT = 60 / BPM          # 0.5 s  -> every scene boundary in index.html sits on this grid
rng = np.random.default_rng(7)


# ----------------------------------------------------------------- helpers
def tv(d):
    return np.arange(int(d * SR)) / SR


def noise(d):
    return rng.standard_normal(int(d * SR))


def sos(kind, fc, order=4):
    return signal.butter(order, fc, btype=kind, fs=SR, output="sos")


def lp(x, fc, order=4):
    return signal.sosfilt(sos("low", fc, order), x)


def hp(x, fc, order=4):
    return signal.sosfilt(sos("high", fc, order), x)


def bp(x, lo, hi, order=3):
    return signal.sosfilt(sos("band", [lo, hi], order), x)


def decay(d, tau):
    return np.exp(-tv(d) / tau)


def sweep_phase(f):
    return 2 * np.pi * np.cumsum(f) / SR


def place(buf, sig, t, gain=1.0, pan=0.0):
    """Mix a mono signal into the stereo buffer at time t (equal-power pan)."""
    i = int(round(t * SR))
    if i >= buf.shape[1] or i + len(sig) <= 0:
        return
    a, b = max(0, -i), min(len(sig), buf.shape[1] - i)
    seg = sig[a:b] * gain
    ang = (pan + 1) * np.pi / 4
    buf[0, i + a:i + b] += seg * np.cos(ang)
    buf[1, i + a:i + b] += seg * np.sin(ang)


def fade_in(x, d):
    n = min(len(x), int(d * SR))
    x[:n] *= np.linspace(0, 1, n)
    return x


def fade_out(x, d):
    n = min(len(x), int(d * SR))
    x[-n:] *= np.linspace(1, 0, n)
    return x


# ----------------------------------------------------------------- instruments
def kick(vol=1.0):
    t = tv(0.42)
    f = 46 + 130 * np.exp(-t / 0.028)
    body = np.sin(sweep_phase(f)) * np.exp(-t / 0.13)
    click = hp(noise(0.42), 2500) * np.exp(-t / 0.004) * 0.25
    return np.tanh(1.6 * (body + click)) * 0.9 * vol


def clap(vol=1.0):
    d = 0.26
    t = tv(d)
    n = bp(noise(d), 900, 5200)
    e = np.zeros_like(t)
    for off in (0, 0.011, 0.022):
        e += np.where(t >= off, np.exp(-(t - off) / 0.006), 0) * 0.6
    e += np.where(t >= 0.03, np.exp(-(t - 0.03) / 0.07), 0)
    return n * e * 0.55 * vol


def snare(vol=1.0, d=0.2):
    t = tv(d)
    tone = np.sin(sweep_phase(190 - 60 * (t / d))) * np.exp(-t / 0.05) * 0.6
    nz = bp(noise(d), 1500, 8000) * np.exp(-t / 0.06)
    return (tone + nz) * 0.6 * vol


def hat(vol=1.0, open_=False):
    d = 0.22 if open_ else 0.06
    return hp(noise(d), 7500) * np.exp(-tv(d) / (0.07 if open_ else 0.018)) * 0.28 * vol


def saw(f, d):
    return signal.sawtooth(2 * np.pi * f * tv(d))


def bass(f, d=0.24, vol=1.0):
    t = tv(d)
    x = 0.65 * saw(f, d) + 0.5 * np.sin(2 * np.pi * f * t)
    x = lp(x, 520, 2) * np.minimum(1, t / 0.004) * np.exp(-t / 0.18)
    return np.tanh(1.8 * x) * 0.6 * vol


def pad(freqs, d):
    x = np.zeros(int(d * SR))
    t = tv(d)
    for f in freqs:
        for det in (-0.07, 0.0, 0.07):
            x += signal.sawtooth(2 * np.pi * f * (1 + det * 0.01) * t + rng.random() * 6.28)
    x = lp(x, 1500, 2) / (len(freqs) * 3)
    env = np.minimum(1, t / 0.35) * np.minimum(1, (d - t) / 0.25)
    return x * env * 0.5


def pluck(f, d=0.2, vol=1.0):
    t = tv(d)
    x = signal.sawtooth(2 * np.pi * f * t) + 0.5 * signal.square(2 * np.pi * f * 2.003 * t)
    x = lp(x, 3200, 2) * np.minimum(1, t / 0.003) * np.exp(-t / 0.09)
    return x * 0.22 * vol


def boom(d=1.6, vol=1.0):
    t = tv(d)
    f = 34 + 70 * np.exp(-t / 0.18)
    sub = np.sin(sweep_phase(f)) * np.exp(-t / 0.55)
    thump = np.sin(sweep_phase(60 + 160 * np.exp(-t / 0.03))) * np.exp(-t / 0.16)
    return np.tanh(1.5 * (sub * 0.9 + thump * 0.7)) * vol


def crash(d=1.8, vol=1.0):
    t = tv(d)
    n = hp(noise(d), 1800, 3) + 0.4 * bp(noise(d), 500, 1500)
    return n * (np.exp(-t / 0.2) * 0.7 + np.exp(-t / 0.9) * 0.45) * 0.4 * vol


def whoosh(d, vol=1.0, lo=250, hi=5200):
    t = tv(d)
    peak = np.sin(np.pi * (t / d) ** 0.9) ** 2
    out = np.zeros_like(t)
    n = noise(d)
    chunk = int(0.012 * SR)
    prev = None
    for i in range(0, len(t), chunk):
        fc = lo * (hi / lo) ** (i / len(t))
        s = signal.sosfilt(sos("band", [fc * 0.7, min(fc * 1.6, SR / 2 - 100)], 2), n[i:i + chunk])
        out[i:i + chunk] = s
    return out * peak * 1.2 * vol


def riser(d, vol=1.0, lo=200, hi=7000, rev=True):
    t = tv(d)
    n = noise(d)
    out = np.zeros_like(t)
    chunk = int(0.01 * SR)
    for i in range(0, len(t), chunk):
        fc = lo * (hi / lo) ** (i / len(t))
        out[i:i + chunk] = signal.sosfilt(sos("band", [fc * 0.6, min(fc * 1.7, SR / 2 - 100)], 2), n[i:i + chunk])
    tone = np.sin(sweep_phase(110 * (1100 / 110) ** (t / d))) * 0.35
    env = (t / d) ** 2.2
    return (out * 1.1 + tone) * env * vol


def thump(d=0.11, f0=150, f1=55, vol=1.0):
    t = tv(d)
    x = np.sin(sweep_phase(f1 + (f0 - f1) * np.exp(-t / 0.02))) * np.exp(-t / 0.045)
    x += hp(noise(d), 3000) * np.exp(-t / 0.004) * 0.25
    return x * vol


def blip(f, d=0.09, vol=1.0):
    t = tv(d)
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2 * t)) * np.exp(-t / 0.035) * vol * 0.5


def zap(d=0.18, f0=2400, f1=300, vol=1.0):
    t = tv(d)
    return np.sin(sweep_phase(f0 * (f1 / f0) ** (t / d))) * np.exp(-t / 0.06) * vol


# ----------------------------------------------------------------- music
CHORDS = [  # Am | F | C | G
    dict(root=55.00, notes=[220.00, 261.63, 329.63]),
    dict(root=43.65, notes=[174.61, 220.00, 261.63]),
    dict(root=65.41, notes=[261.63, 329.63, 392.00]),
    dict(root=49.00, notes=[196.00, 246.94, 293.73]),
]
BASS_SLOTS = [0, 1, 3, 4, 6, 7]   # eighth-note slots of the bar that carry bass


def groove(music, bed, start, end, full=True, lead=False, first_bar=0):
    """Drum + bass + pad (+ lead) groove between start and end (bar = 2 s)."""
    kicks = []
    bar = 0
    t0 = start
    while t0 < end - 1e-6:
        ch = CHORDS[(first_bar + bar) % 4]
        L = min(4 * BEAT, end - t0)
        if L > 0.5:
            place(bed, pad(ch["notes"], L + 0.05), t0, 0.5)
        for b in range(4):
            tb = t0 + b * BEAT
            if tb >= end:
                break
            place(music, kick(), tb, 0.9)
            kicks.append(tb)
            if b in (1, 3):
                place(music, clap(), tb, 0.8)
            if full:
                place(music, hat(open_=True), tb + BEAT / 2, 0.7)
                place(music, hat(), tb, 0.5)
                place(music, hat(), tb + BEAT / 4, 0.28)
                place(music, hat(), tb + BEAT * 3 / 4, 0.28)
        for s in BASS_SLOTS:
            ts = t0 + s * BEAT / 2
            if ts < end:
                f = ch["root"] * (2 if s == 7 else 1)
                place(bed, bass(f, 0.2), ts, 0.95)
        if lead:
            arp = [0, 1, 2, 1, 0, 1, 2, 1]
            for s in range(8):
                ts = t0 + s * BEAT / 2
                if ts < end:
                    place(bed, pluck(ch["notes"][arp[s]] * 2, 0.22), ts, 0.8, pan=(-0.35 if s % 2 else 0.35))
        t0 += 4 * BEAT
        bar += 1
    return kicks


def sidechain(bed, kicks, depth=0.65, rel=0.11):
    duck = np.ones(bed.shape[1])
    for kt in kicks:
        i = int(kt * SR)
        n = int(0.4 * SR)
        j = min(i + n, len(duck))
        seg = 1 - depth * np.exp(-np.arange(j - i) / SR / rel)
        duck[i:j] = np.minimum(duck[i:j], seg)
    return bed * duck


# ----------------------------------------------------------------- main
def main(cues_path, out_path):
    data = json.load(open(cues_path))
    dur = data["duration"]
    cues = data["cues"]
    N = int(dur * SR)
    sfx = np.zeros((2, N))
    music = np.zeros((2, N))
    bed = np.zeros((2, N))     # pads / bass / lead (sidechained)

    def first(name):
        return next(c for c in cues if c["n"] == name)

    t_on, t_break = first("music_on")["t"], first("breakdown")["t"]
    t_drop, t_out = first("drop")["t"], first("music_out")["t"]
    t_hit = first("impact")["t"]

    # --- title: pad swell + sparse pulse leading into the groove
    place(bed, pad(CHORDS[0]["notes"], t_on - t_hit + 0.3), t_hit, 0.55)
    place(bed, bass(CHORDS[0]["root"], 1.8), t_hit, 0.7)
    for k, tb in enumerate(np.arange(t_hit + 1.0, t_on, BEAT)):
        place(music, kick(), tb, 0.6 + 0.1 * k)
        place(music, hat(), tb + BEAT / 2, 0.5)
    k1 = [t for t in np.arange(t_hit + 1.0, t_on, BEAT)]

    # --- groove: red scene (lead enters with the blue scene)
    blue_s = next(c for c in cues if c["n"] == "whoosh" and abs(c["t"] - 7.0) < 0.01)["t"]
    k2 = groove(music, bed, t_on, blue_s, full=True, lead=False, first_bar=0)
    k3 = groove(music, bed, blue_s, t_break, full=True, lead=True, first_bar=2)

    # --- breakdown: pad + snare roll + riser
    place(bed, pad([220.0, 261.63, 329.63], t_drop - t_break + 0.05), t_break, 0.5)
    tt = t_break
    step = BEAT / 2
    while tt < t_drop - 1e-6:
        prog = (tt - t_break) / (t_drop - t_break)
        place(music, snare(0.5 + 0.7 * prog, 0.16), tt, 1.0)
        step = BEAT / 2 if prog < 0.5 else (BEAT / 4 if prog < 0.8 else BEAT / 8)
        tt += step
    # --- drop: full groove
    k4 = groove(music, bed, t_drop, t_out, full=True, lead=True, first_bar=0)

    bed = sidechain(bed, k1 + k2 + k3 + k4, depth=0.6)
    # duck everything for 35 ms right before the drop so the hit punches
    gap = np.ones(N)
    gi, gj = int((t_drop - 0.035) * SR), int(t_drop * SR)
    gap[gi:gj] = np.linspace(1, 0.05, gj - gi)
    music *= gap
    bed *= gap

    # --- sound effects
    for c in cues:
        n, t = c["n"], c["t"]
        if n == "riser":
            place(sfx, riser(c["dur"], lo=150, hi=6500), t, 0.55)
        elif n == "riser2":
            place(sfx, riser(c["dur"], lo=300, hi=9000), t, 0.85)
        elif n == "impact":
            big = c.get("big", 1)
            place(sfx, boom(1.8 if big == 1 else 2.6), t, 1.0 if big == 1 else 1.25)
            place(sfx, crash(1.9 if big == 1 else 2.6), t, 0.7 if big == 1 else 1.0)
            place(sfx, zap(0.25, 3200, 200), t, 0.25)
        elif n == "whoosh":
            place(sfx, whoosh(c["dur"] + 0.1), t - 0.05, 0.75, pan=c.get("pan", 0) * 0.5)
        elif n == "tick":
            place(sfx, thump(0.1, 170 - 6 * c["i"], 60), t, 0.55, pan=(c["i"] - 3.5) / 5)
        elif n == "split":
            place(sfx, zap(0.3, 2200, 500), t, 0.22)
        elif n == "blip":
            place(sfx, blip(880), t, 0.5)
            place(sfx, blip(1320), t + 0.07, 0.5)
        elif n == "clash":
            place(sfx, thump(0.2, 130, 45), t, 0.9)
            place(sfx, hp(noise(0.12), 2000) * decay(0.12, 0.03), t, 0.35)
        elif n == "slam":
            place(sfx, thump(0.28, 110, 38), t, 1.0)
            place(sfx, hp(noise(0.2), 1500) * decay(0.2, 0.05), t, 0.45)
        elif n == "card":
            side = 0.45 if c["team"] == "red" else -0.45
            place(sfx, snare(0.0 + 0.8, 0.12), t, 0.6, pan=side)
            place(sfx, thump(0.12, 190 + 10 * c["i"], 70), t, 0.6, pan=side)
            place(sfx, blip(660 * 2 ** (c["i"] / 6), 0.07), t + 0.01, 0.35, pan=side)
        elif n == "tick2":
            place(sfx, blip(520 * 2 ** (c["i"] / 6), 0.06), t, 0.35, pan=-0.5)
            place(sfx, blip(520 * 2 ** (c["i"] / 6), 0.06), t + 0.01, 0.35, pan=0.5)
        elif n == "whiteout":
            place(sfx, riser(c["dur"], lo=500, hi=11000), t, 0.9)

    # --- master
    mix = sfx * 1.0 + music * 0.78 + bed * 0.82
    # gently tuck the music under the big hits
    mix = np.tanh(mix * 1.15) / np.tanh(1.15)
    mix = lp(mix, 17500, 2)
    # final fade (whiteout ends the clip)
    for ch in range(2):
        fade_out(mix[ch], 0.08)
        fade_in(mix[ch], 0.01)
    peak = np.max(np.abs(mix))
    mix = mix / peak * 0.85
    pcm = (mix.T * 32767).astype("<i2")
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    rms = 20 * np.log10(np.sqrt(np.mean(mix ** 2)) + 1e-9)
    print(f"audio -> {out_path}  ({dur:.2f}s, peak 0.85, rms {rms:.1f} dBFS)")


if __name__ == "__main__":
    main(*(sys.argv[1:3] if len(sys.argv) >= 3 else ("build/cues.json", "build/audio.wav")))
