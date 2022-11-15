from mingus.core import chords, notes, keys, scales
from aleatora import *
from aleatora import alternator
import reapy

def arp(chord_name):
    ns = chords.from_shorthand(chord_name)
    ps = [60 + notes.note_to_int(n) for n in ns]
    # TODO use `note()` helper
    return [{"start": i/4, "end": (i+1)/4, "pitch": p} for i, p in enumerate(ps*4)]

# most convenient music theory library in python? maybe just music21
# def transpose(thing, amount, scale):
#     return [{"pitch": }]

csound_wasm = alternator.wasm("/home/ian/GT/alternator/alternator/wasm/csound-example-bundle")
python_wasm = alternator.wasm("/home/ian/GT/alternator/alternator/wasm/python-example-bundle")

reapy.print("hello?")
