from math import *
from random import *

from mingus.core import chords, notes, keys, scales
import music21 as m21

from aleatora import *
from aleatora import alternator

def note(start, dur, pitch, **args):
    return {"start": start, "end": start + dur, "pitch": pitch, **args}

def transpose(notes, amount, scale=None):
    if scale is None:
        return [{**note, "pitch": note["pitch"] + amount} for note in notes]
    else:
        scale = m21.scale.MajorScale(scale) if scale.isupper() else m21.scale.MinorScale(scale)
        return [{**note, "pitch": scale.nextPitch(m21.pitch.Pitch(note["pitch"]), stepSize=amount).midi} for note in notes]


def arp(chord_name):
    ns = chords.from_shorthand(chord_name)
    ps = [60 + notes.note_to_int(n) for n in ns]
    return [note(i/4, 1/4, p) for i, p in enumerate(ps*4)]

# most convenient music theory library in python? maybe just music21
# def transpose(thing, amount, scale):
#     return [{"pitch": }]

csound_wasm = alternator.wasm("/home/ian/GT/alternator/alternator/wasm/csound-example-bundle")
python_wasm = alternator.wasm("/home/ian/GT/alternator/alternator/wasm/python-example-bundle")
