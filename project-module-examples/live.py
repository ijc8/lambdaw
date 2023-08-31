import lambdaw
from aleatora import *

# Here, we override LambDAW's default behavior to
# control how it converts Python values into DAW items.
def custom_convert_output(output, *args):
    # `output` may be a (potentially endless) iterable.
    # So, we peek at the first item in order to determine the type.
    first, output = lambdaw.peek(output)
    if isinstance(first, tuple):
        output = midi.events_to_notes(output)
    # Fallback to default converter for any other type.
    return lambdaw.convert_output(output, *args)

lambdaw.register_converters(output=custom_convert_output)


from random import *
import reapy

Scale.default = "dorian"
project = reapy.Project()

def p(pattern, *args, **kwargs):
    return beat(P+(pattern), dur=project.time_signature[1], *args, **kwargs)

def t(pattern, *args, **kwargs):
    return tune(P+(pattern), dur=project.time_signature[1], *args, **kwargs)

def transpose(notes, offset):
    return [{**note, "pitch": note["pitch"] + offset} for note in notes]

# Experiment with Vortex for Tidal notation.
# (Requires latest: `pip install "tidalvortex @ git+https://github.com/tidalcycles/vortex@main"`)
import re
import numbers
import vortex
from vortex import note  # for use in expressions

note_regex = re.compile("([A-Ga-g])([#b]?)(\d*)")
note_names = "cdefgab"
major_scale = [0, 2, 4, 5, 7, 9, 11]
accidentals = {'': 0, '#': 1, 'b': -1}

def note_to_pitch(note):
    if isinstance(note, numbers.Real):
        return note
    name, accidental, octave = note_regex.match(note).groups()
    name = name.lower()
    accidental = accidentals[accidental]
    octave = int(octave) if octave else 4
    return major_scale[note_names.index(name)] + accidental + (octave + 1) * 12

# TODO: Try custom converter for `vortex.Pattern` instead of using `n()`;
#       consider using length of item to determine number of cycles rather than taking argument.
# Ex:
#   =n("c d e g")
#   =n("c [e g] <a*3 b*3> c5*4", 2)
#   =n(note("e d c d e e e ~").slow(2), 2)
def n(pattern, cycles=1):
    if isinstance(pattern, str):
        pattern = vortex.note(pattern)
    for event in pattern.query(vortex.TimeSpan(0, cycles)):
        # TODO: Respect cycle length / project time signature
        yield {"pitch": note_to_pitch(event.value["note"]), "start": float(event.part.begin), "end": float(event.part.end)}


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
        result = wav.load(path)
    return result


# Experiment with MusicVAE

# Same issue as RAVE: we'd like to run the model directly,
# but importing Tensorflow causes REAPER to deadlock.

import ast

def musicvae(model):
    result = subprocess.run(["python", "run_musicvae.py", model], capture_output=True)
    if result.returncode:
        raise RuntimeError("Failed to run MusicVAE:\n" + result.stderr.decode("utf8"))
    return ast.literal_eval(result.stdout.decode("utf8"))
