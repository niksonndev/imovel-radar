#!/usr/bin/env python3
# Imóvel Radar 15s — sound score: palette in one room, music-less, dynamics follow the picture
import sys, pathlib
sys.path.insert(0, str(pathlib.Path("/home/nikson/.hermes/skills/creative/onetake/scripts")))
import numpy as np
from sfx_palette import SR, air, glass, wood, sub, bubble, pan_of, Score

DUR = 15.0
s = Score(dur=DUR, T60=1.05)

def keys(t, n=3, gain=0.22, start=0.4, step=0.045, cps=44):
    for i in range(n):
        s.place(wood(170 + (i % 3) * 22, 0.09), t + start + i * step, gain * (1 - 0.15 * (i % 3)), pan_of(700), 0.15)

def tap(t, x=1200, gain=0.5):
    s.place(wood(230, 0.07), t, gain, pan_of(x), 0.25)
    s.place(glass(720, 0.25, 0.7), t + 0.02, gain * 0.6, pan_of(x), 0.4)

def ping(t, x=960, gain=0.6):
    s.place(glass(880, 0.5, 1.0), t, gain, pan_of(x), 0.5)
    s.place(glass(1320, 0.4, 0.7), t + 0.06, gain * 0.4, pan_of(x), 0.5)

def pop(t, x=580, gain=0.5):
    s.place(bubble(430, 0.2), t, gain, pan_of(x), 0.35)

def whoosh(t, gain=0.4):
    s.place(air(0.5, 300, 2600, 1.4, 0.4), t, gain, 0, 0.6)

def riser(t, gain=0.35):
    s.place(air(1.1, 220, 3200, 1.2, 0.5), t, gain, 0, 0.6)

def thud(t, gain=0.6):
    s.place(sub(66, 0.5), t, gain, 0, 0.5)

# BEAT 1 · typing + send + chips
keys(0.4, n=10, gain=0.2, step=0.05, start=0)
tap(2.6, 1280, 0.55)                     # send
for i in range(5): pop(2.72 + i*0.06, 650 + i*160, 0.4)   # chips
ping(3.7, 960, 0.5)                      # radar sweep
# BEAT 2 · card lands
whoosh(4.0, 0.35)
tap(4.35, 900, 0.5)                      # card pop
# BEAT 3 · "acompaña este" send + morph
keys(5.8, n=6, gain=0.18, step=0.05, start=0)
tap(7.15, 960, 0.45)                     # morph land
# BEAT 4 · stillness: single faint ping on the pulse
ping(8.5, 1000, 0.25)
# BEAT 5 · price rolls; riser then tap; typing
riser(9.7, 0.3)
thud(10.25, 0.55)                        # price hits R$1.800
keys(10.35, n=8, gain=0.18, step=0.05, start=0)
# BEAT 6 · market in, fold, end
pop(11.7, 760, 0.45)
thud(13.15, 0.5)
tap(13.5, 960, 0.5)                      # end rest settle
# gentle low pad so it isn't silent under a busy wall: an air bed at start + tail
s.place(air(1.4, 150, 320, 1.6, 0.6), 0.1, 0.12, 0, 0.5)

s.write("sfx.wav", peak_db=-8.0)