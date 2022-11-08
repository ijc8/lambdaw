import array
import math
import random
import os
import wave
from typing import List

import reapy

def generate_wave(filename):
    # NOTE: Avoiding numpy due to segfault on reload: https://github.com/numpy/numpy/issues/11925
    sample_rate = 48000
    wav = wave.open(filename, "w")
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(sample_rate)
    scale = random.random() * (2**15 - 1)
    freq = random.randrange(220, 440)
    audio = array.array('h', (
        round(math.sin(2*math.pi * i/sample_rate * freq) * scale)
        for i in range(sample_rate * 5)
    ))
    wav.writeframes(audio)
    wav.close()

p = reapy.Project()
audio_dir = os.path.join(p.path, "lambdaw")
os.makedirs(audio_dir, exist_ok=True)

# Setup namespace for user code
def note(start, dur, pitch, **args):
    return {"start": start, "end": start + dur, "pitch": pitch, **args}

def transpose(notes, amount):
    return [{**note, "pitch": note["pitch"] + amount} for note in notes]

namespace = {"note": note, "transpose": transpose, **{key: getattr(random, key) for key in random.__all__}}

to_derive: List[reapy.Take] = []

with reapy.undo_block("Evaluate all clips"):
    for track_index, track in enumerate(p.tracks):
        for item_index, item in enumerate(track.items):
            take = item.active_take
            if take.name.startswith("="):
                # Derived clip
                to_derive.append((track_index, item_index, take))
            else:
                namespace[take.name] = [note.infos for note in take.notes]
    for track_index, item_index, take in to_derive:
        print(take.name)
        if take.name == "=!test":
            filename = f"track{track_index}_item{item_index}.wav"
            filename = os.path.join(audio_dir, filename)
            generate_wave(filename)
            if take.source.filename != filename:
                # TODO: In what circumstances do we need to delete the old source?
                source = reapy.RPR.PCM_Source_CreateFromFile(filename)
                reapy.RPR.SetMediaItemTake_Source(take.id, source)
            continue
        notes = eval(take.name[1:], namespace)
        # Clear current notes
        while take.n_notes:
            take.notes[0].delete()
        for note in notes:
            take.add_note(**note)

# TODO: Instead use command 40441 to rebuild only peaks for generated audio clips.
reapy.RPR.Main_OnCommand(40048, 0)
