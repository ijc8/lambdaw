# Import things from standard library that we want to use in expressions.
# Convenient to have sin, cos, etc.
from math import *
# and randrange, choice, and co.
from random import *


# Music theory
from mingus.core import chords, notes
import music21 as m21

def note(start, dur, pitch, **args):
    return {"start": start, "end": start + dur, "pitch": pitch, **args}

def arp(chord_name):
    ns = chords.from_shorthand(chord_name)
    ps = [60 + notes.note_to_int(n) for n in ns]
    return [note(i/4, 1/4, p) for i, p in enumerate(ps*4)]

def transpose(notes, amount, scale=None):
    if scale is None:
        return [{**note, "pitch": note["pitch"] + amount} for note in notes]
    else:
        scale = m21.scale.MajorScale(scale) if scale.isupper() else m21.scale.MinorScale(scale)
        return [{**note, "pitch": scale.nextPitch(m21.pitch.Pitch(note["pitch"]), stepSize=amount).midi} for note in notes]


# For audio examples (in this project; used for MIDI in other example modules.)
from aleatora import *

# Wasm experiment
from aleatora import alternator
csound_wasm = alternator.wasm("/home/ian/GT/alternator/alternator/wasm/csound-example-bundle")
python_wasm = alternator.wasm("/home/ian/GT/alternator/alternator/wasm/python-example-bundle")


# Generator example
def fib():
    a, b = 1, 1
    yield a
    yield b
    while True:
        a, b = b, a + b
        yield b

def fib_tune(d):
    return (note(i/8, 1/8, x) for i, x in zip(range(d), fib()))


# You can also use the ReaScript API (here via reapy) from expressions.
import reapy

# Wrap an expression with this to display a message upon evaluation.
def log(x):
    reapy.print(x)
    return x
