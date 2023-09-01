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

tr = transpose

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


# Experiment with RAVE

# This would be ideal, but unfortunately it doesn't work because importing PyTorch causes REAPER to deadlock:
# from aleatora.rave import rave
# vintage = rave("vintage.ts")

# The multiprocessing module also doesn't work within REAPER. :-(

# So, for the moment, we do it in a hacky way: just run RAVE in a separate Python process.
# (Long-term solution is to just do all evaluation in a separate Python process.)
import os
import subprocess
import tempfile

def rave(model_path, audio):
    with tempfile.TemporaryDirectory() as dir:
        path = os.path.join(dir, "tmp.wav")
        wav.save(audio, path)
        if subprocess.run(["python", "run_rave.py", model_path + ".ts", path, path]).returncode:
            raise RuntimeError("Failed to run RAVE")
        return wav.load(path)


# Experiment with MusicVAE

# Same issue as RAVE: we'd like to run the model directly,
# but importing Tensorflow causes REAPER to deadlock.

import ast

def musicvae(model):
    result = subprocess.run(["python", "run_musicvae.py", model], capture_output=True)
    if result.returncode:
        raise RuntimeError("Failed to run MusicVAE:\n" + result.stderr.decode("utf8"))
    return ast.literal_eval(result.stdout.decode("utf8"))


# Use DECTalk to speak and sing.
# (See https://github.com/dectalk/dectalk)
def say(text):
    with tempfile.TemporaryDirectory() as dir:
        path = os.path.join(dir, "tmp.wav")
        if subprocess.run(["./say", "-fo", path, "-a", text]).returncode:
            raise RuntimeError("Failed to run DECTalk")
        return wav.load(path, resample=True)


# def sing(*tune: List[Union[str, Tuple[float, int]]]):
    # "tune: list of (phoneme in ARPAbet, duration in seconds, pitch from baseline)"
    # text = ' '.join(f"{phoneme}<{round(seconds * 1000)},{pitch}>" for phoneme, seconds, pitch in tune)
def sing(text):
    text = f"[:phone on] [{text}]"
    with tempfile.TemporaryDirectory() as dir:
        path = os.path.join(dir, "tmp.wav")
        if subprocess.run(["./say", "-fo", path, "-a", text]).returncode:
            raise RuntimeError("Failed to run DECTalk")
        return wav.load(path, resample=True)


def prompt(min=0, max=100):
    p = subprocess.run(["zenity", "--scale", "--min-value", str(min), "--max-value", str(max)], capture_output=True)
    return float(p.stdout.decode("utf8"))

# Experiment with py5
from PIL import Image

def py5_test(demo):
    with tempfile.TemporaryDirectory() as dir:
        if subprocess.run(["python", "run_py5.py", demo, dir]).returncode:
            raise RuntimeError("Failed to run py5")
        for frame in sorted(os.listdir(dir)):
            yield np.asarray(Image.open(os.path.join(dir, frame)))
