import aleatora.streams.audio
import array
import itertools
import os
import wave

import reapy

sample_rate = 48000
aleatora.streams.audio.SAMPLE_RATE = sample_rate

def generate_wave(filename, it):
    # NOTE: Avoiding numpy due to segfault on reload: https://github.com/numpy/numpy/issues/11925
    wav = wave.open(filename, "w")
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(sample_rate)
    scale = 2**15 - 1
    audio = array.array('h', (int(x * scale) for x in it))
    wav.writeframes(audio)
    wav.close()

def create_midi_source(take):
    # Create a new, blank MIDI source that is the length of its container.
    # This is weirdly complicated. See https://forum.cockos.com/showthread.php?t=100864.
    size = 4*1024*1024  # see reaper_python's `rpr_packs()`
    source = reapy.RPR.PCM_Source_CreateFromType("MIDI")
    reapy.RPR.SetMediaItemTake_Source(take.id, source)
    ticks = int(reapy.RPR.get_config_var_string("miditicksperbeat", 0, size)[2])
    state = reapy.RPR.GetItemStateChunk(take.item.id, 0, size, True)[2]
    project = reapy.Project()
    start = project.time_to_beats(take.item.position)
    end = project.time_to_beats(take.item.position + take.item.length)
    payload = f"""
<SOURCE MIDI
HASDATA 1 {ticks} QN
E {int(ticks*(end - start))} b0 7b 00
>
""".strip().split("\n")
    lines = state.split("\n")
    start_index = next(i for i, line in enumerate(lines) if line.startswith("<SOURCE MIDI"))
    end_index = lines.index(">", start_index + 1)
    lines[start_index:end_index + 1] = payload
    state = "\n".join(lines)
    reapy.RPR.SetItemStateChunk(take.item.id, state, size)

def peek(it):
    try:
        first = next(it)
    except StopIteration:
        return None
    return (first, itertools.chain((first,), it))

def eval_takes(selected=False):
    generated_audio = False
    for track_index, item_index, item, take in to_eval:
        if selected and not item.is_selected:
            continue
        # Add parenthesis to shorten common case of generator expressions.
        output = iter(eval("(" + take.name[1:] + ")", namespace))
        # Clear current notes
        while take.n_notes:
            take.notes[0].delete()
        peeked = peek(output)
        if peeked is None: continue
        first, output = peeked
        if isinstance(first, dict):
            if not take.is_midi:
                create_midi_source(take)
            for note in output:
                take.add_note(**note)
        else:
            filename = f"track{track_index}_item{item_index}.wav"
            filename = os.path.join(audio_dir, filename)
            generate_wave(filename, itertools.islice(output, int(take.item.length * sample_rate)))
            if take.source.filename != filename:
                # TODO: In what circumstances do we need to delete the old source?
                source = reapy.RPR.PCM_Source_CreateFromFile(filename)
                reapy.RPR.SetMediaItemTake_Source(take.id, source)
            generated_audio = True

    if generated_audio:
        # TODO: Instead use command 40441 to rebuild only peaks for generated audio clips.
        reapy.RPR.Main_OnCommand(40048, 0)

# Functions for user code
def note(start, dur, pitch, **args):
    return {"start": start, "end": start + dur, "pitch": pitch, **args}

def transpose(notes, amount):
    return [{**note, "pitch": note["pitch"] + amount} for note in notes]

# Setup namespace for user code
namespace = {"note": note, "transpose": transpose, "sr": sample_rate}
exec("from aleatora import *; from math import *; from random import *", namespace)

# NOTE: Even if we're only re-evaluating a subset of items,
# the namespace needs to contain all items so user code can refer to them.
to_eval = []
for track_index, track in enumerate(reapy.Project().tracks):
    for item_index, item in enumerate(track.items):
        take = item.active_take
        if take.name.startswith("="):
            # Expression clip: may need to evaluate name
            to_eval.append((track_index, item_index, item, take))
        else:
            namespace[take.name] = [note.infos for note in take.notes]

# Make directory for generated audio clips
audio_dir = os.path.join(reapy.Project().path, "lambdaw")
os.makedirs(audio_dir, exist_ok=True)
