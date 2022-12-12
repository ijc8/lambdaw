import aleatora.streams.audio
import array
import importlib
import itertools
import os
from pathlib import Path
import sys
import time
import wave

import reapy

sample_rate = 48000
aleatora.streams.audio.SAMPLE_RATE = sample_rate

def generate_wave(path, it):
    # NOTE: Avoiding numpy due to segfault on reload: https://github.com/numpy/numpy/issues/11925
    wav = wave.open(path, "w")
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(sample_rate)
    scale = 2**15 - 1
    audio = array.array('h', (int(max(-1, min(x, 1)) * scale) for x in it))
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

def collect_garbage():
    # Delete unused lambdaw-generated audio files & reapeaks.
    files = {os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.endswith(".wav")}
    used = set()
    # TODO: Maybe avoid going through all the project contents again here.
    # Instead, perhaps we could get this information in `scan_items` and update it appropriately in `eval_takes`.
    for track in reapy.Project().tracks:
        for item in track.items:
            for take in item.takes:
                used.add(os.path.abspath(take.source.filename))
    unused = files - used
    for file in unused:
        Path(file).unlink()
        Path(file + ".reapeaks").unlink(True)

# TODO: Maybe make the conversions user-customizable via project module?
def convert_input(take):
    take_start = take.item.position - take.start_offset
    def convert_note(note):
        infos = note.infos
        # TODO: Maybe use beats/PPQ instead of seconds. (The conversion is due to reapy.)
        infos["dur"] = infos["start"] - infos["end"]
        infos["start"] -= take_start
        infos["end"] -= take_start
        return infos
    # TODO: Also handle audio takes
    return [convert_note(note) for note in take.notes]

def convert_output(output, track_index, item_index, take):
    def convert_note(note):
        # NOTE: We don't add back `take_start` here due to reapy inconsistency.
        if "dur" in note:
            del note["dur"]
        return note
    # Clear current notes
    while take.n_notes:
        take.notes[0].delete()
    peeked = peek(output)
    if peeked is None:
        return
    first, output = peeked
    if isinstance(first, dict):
        if not take.is_midi:
            create_midi_source(take)
        for note in output:
            take.add_note(**convert_note(note))
        return False
    else:
        path = os.path.join(audio_dir, f"track{track_index}_item{item_index}_{time.monotonic_ns()}.wav")
        generate_wave(path, itertools.islice(output, int(take.item.length * sample_rate)))

        source = reapy.RPR.PCM_Source_CreateFromFile(os.path.join(lambdaw_dir, path))
        old_source = take.source
        reapy.RPR.SetMediaItemTake_Source(take.id, source)
        if Path(old_source.filename).is_relative_to(audio_dir):
            reapy.RPR.PCM_Source_Destroy(old_source.id)
        return True

def build_peaks(source):
    result = reapy.RPR.PCM_Source_BuildPeaks(source.id, 0)
    reapy.print(0, result)
    if result != 0:
        while (result := reapy.RPR.PCM_Source_BuildPeaks(source.id, 1)) != 0:
            reapy.print(1, result)
    reapy.RPR.PCM_Source_BuildPeaks(source.id, 2)

def eval_takes(take_info):
    generated_audio = False
    for name, expression, track_index, item_index, take in take_info:
        # Add parenthesis to shorten common case of generator expressions.
        output = iter(eval("(" + expression + ")", namespace))
        rebuild_peaks = convert_output(output, track_index, item_index, take)
        if rebuild_peaks:
            build_peaks(take.source)
        generated_audio |= rebuild_peaks

    if generated_audio:
        collect_garbage()
        reapy.update_arrange()

    reapy.RPR.Undo_OnStateChange2(reapy.Project().id, f"lambdaw: evaluate expressions")

# Setup namespace for user code
namespace = {"sr": sample_rate}

lambdaw_dir = os.path.join(reapy.Project().path, "lambdaw")
audio_dir = os.path.abspath(os.path.join(lambdaw_dir, "audio"))

# Make directory for generated audio clips
os.makedirs(audio_dir, exist_ok=True)
os.chdir(lambdaw_dir)

module_path = Path("project.py")
if not module_path.exists():
    module_path.touch()

sys.path.append(lambdaw_dir)
if "project" in sys.modules:
    importlib.reload(sys.modules["project"])
exec("from project import *", namespace)

def scan_items():
    # NOTE: Even if we're only re-evaluating a subset of items,
    # the namespace needs to contain all items so user code can refer to them.
    snippets = {}
    for track_index, track in enumerate(reapy.Project().tracks):
        for item_index, item in enumerate(track.items):
            take = item.active_take
            var_name, *expression = take.name.split("=", 1)
            expression = expression[0] if expression else None
            if expression:
                # Expression item: may need evaluation
                snippets[take.id] = (take.name, expression, track_index, item_index, take)
            namespace[var_name] = convert_input(take)
    return snippets

snippets = scan_items()
project = reapy.Project()

counter = 0

CYCLE_LENGTH = 2  # seconds

def execute(pending):
    global counter, snippets, project
    if not (pending or counter > 3):
        # Don't check for updates every time.
        counter += 1
        return
    counter = 0

    # Check for expressions in track names (livecoding mode)
    if project.is_playing:
        for track in project.tracks:
            if track.name.startswith("="):
                reapy.print(track.name, project.play_position)
                next_cycle_start = (project.play_position // CYCLE_LENGTH + 1) * CYCLE_LENGTH
                next_cycle_end = next_cycle_start + CYCLE_LENGTH
                for item in track.items:
                    if item.position < next_cycle_end and item.position + item.length > next_cycle_start:
                        break  # found an item there already
                else:
                    item = track.add_item(next_cycle_start, next_cycle_end)
                    take = item.add_take()
                    reapy.RPR.GetSetMediaItemTakeInfo_String(take.id, "P_NAME", track.name, True)

    # Check for new/updated expressions in take names
    old_snippets = snippets
    snippets = scan_items()
    changed = set()
    # Don't scan for renamed clips if the user switched projects.
    # TODO: Better support for working in multiple projects.
    for key, value in snippets.items():
        if key not in old_snippets or old_snippets[key][0] != value[0]:
            changed.add(key)
    if changed or pending:
        # reapy.print("changed:", {id: snippets[id][0] for id in changed})
        filter = {
            "eval_all": lambda _: True,
            "eval_selected": lambda take: take.item.is_selected or take.id in changed,
            "": lambda take: take.id in changed,
        }[pending]
        eval_takes(v for v in snippets.values() if filter(v[-1]))
