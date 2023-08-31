import array
import importlib
import itertools
import os
from pathlib import Path
import sys
import time
import traceback
import wave

import ffmpeg
import numpy as np
import reapy

SAMPLE_RATE = 48000

def generate_wave(name, it):
    # NOTE: Avoiding numpy due to segfault on reload: https://github.com/numpy/numpy/issues/11925
    path = os.path.join(media_dir, name + ".wav")
    wav = wave.open(path, "w")
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(SAMPLE_RATE)
    scale = 2**15 - 1
    audio = array.array('h', (int(max(-1, min(x, 1)) * scale) for x in it))
    wav.writeframes(audio)
    wav.close()
    return path

def generate_video(name, it):
    path = os.path.join(media_dir, name + ".mp4")
    fps = 30
    width, height = 1280, 720
    process = (
        ffmpeg
            .input('pipe:', format='rawvideo', pix_fmt='rgb24', s='{}x{}'.format(width, height), framerate=fps)
            .output(path, pix_fmt='yuv420p', vcodec='libx264', r=fps)
            .overwrite_output()
            .run_async(pipe_stdin=True)
    )

    for i, frame in enumerate(it):
        process.stdin.write((frame * 255).astype(np.uint8))

    process.stdin.close()
    process.wait()
    return path

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

def peek(iterable, default=None):
    it = iter(iterable)
    try:
        first = next(it)
    except StopIteration:
        return (default, ())
    return (first, itertools.chain((first,), it))

def collect_garbage():
    # Delete unused lambdaw-generated audio files & reapeaks.
    files = {os.path.join(media_dir, f) for f in os.listdir(media_dir) if f.startswith("track")}
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

def convert_input(take: reapy.Take):
    take_start = take.item.position - take.start_offset
    def convert_note(note):
        infos = note.infos
        # TODO: Maybe use beats/PPQ instead of seconds. (The conversion is due to reapy.)
        infos["dur"] = infos["start"] - infos["end"]
        infos["start"] -= take_start
        infos["end"] -= take_start
        return infos
    if take.is_midi:
        return [convert_note(note) for note in take.notes]
    else:
        def generator():
            accessor = take.add_audio_accessor()
            length = int((accessor.end_time - accessor.start_time) * SAMPLE_RATE)
            chunk_size = 4096
            for i in range(0, length, chunk_size):
                chunk = accessor.get_samples(i / SAMPLE_RATE, chunk_size, sample_rate=SAMPLE_RATE)
                yield from chunk
            # TODO: Does accessor still get cleaned up if expression doesn't exhaust this generator?
            # I suspect not. Might need to implement __del__ on something - ideally reapy's AudioAccessor class.
            accessor.delete()
        return generator()


def convert_output(output, track_index, item_index, take):
    def convert_note(note):
        # NOTE: We don't add back `take_start` here due to reapy inconsistency.
        if "dur" in note:
            del note["dur"]
        return note
    # Clear current notes
    while take.n_notes:
        take.notes[0].delete()
    if output is None:
        output = ()
    peeked = peek(output)
    first, output = peeked
    if isinstance(first, dict):
        if not take.is_midi:
            create_midi_source(take)
        for note in output:
            take.add_note(**convert_note(note))
        return False
    else:
        name = f"track{track_index}_item{item_index}_{time.monotonic_ns()}"
        if isinstance(first, np.ndarray):
            path = generate_video(name, output)
        else:
            path = generate_wave(name, itertools.islice(output, int(take.item.length * SAMPLE_RATE)))

        source = reapy.RPR.PCM_Source_CreateFromFile(os.path.join(lambdaw_dir, path))
        old_source = take.source
        reapy.RPR.SetMediaItemTake_Source(take.id, source)
        if Path(old_source.filename).is_relative_to(media_dir):
            reapy.RPR.PCM_Source_Destroy(old_source.id)
        return True

input_converter = convert_input
output_converter = convert_output

def register_converters(input=None, output=None):
    global input_converter, output_converter
    if input is not None:
        input_converter = input
    if output is not None:
        output_converter = output

def build_peaks(source):
    result = reapy.RPR.PCM_Source_BuildPeaks(source.id, 0)
    if result != 0:
        while (result := reapy.RPR.PCM_Source_BuildPeaks(source.id, 1)) != 0:
            pass
    reapy.RPR.PCM_Source_BuildPeaks(source.id, 2)

def eval_takes(take_info):
    generated_audio = False
    for var_name, expression, track_index, item_index, take in take_info:
        if expression is None:
            continue
        try:
            # Add parenthesis to shorten common case of generator expressions.
            output = eval("(" + expression + ")", namespace)
        except:
            if project.is_recording:
                reapy.show_console_message(traceback.format_exc())
            else:
                reapy.show_message_box(traceback.format_exc(), "lambdaw expression")
        else:      
            rebuild_peaks = output_converter(output, track_index, item_index, take)
            # Update value in namespace immediately.
            # reapy.print(f"EVAL: set {var_name} to {namespace[var_name]}")
            namespace[var_name] = input_converter(take)
            if rebuild_peaks:
                build_peaks(take.source)
            generated_audio |= rebuild_peaks

    if generated_audio:
        collect_garbage()
        reapy.update_arrange()

    reapy.RPR.Undo_OnStateChange2(reapy.Project().id, f"lambdaw: evaluate expressions")

# Setup namespace for user code
namespace = {"sr": SAMPLE_RATE}

lambdaw_dir = os.path.join(reapy.Project().path, "lambdaw")
media_dir = os.path.abspath(os.path.join(lambdaw_dir, "audio"))

# Make directory for generated audio clips
os.makedirs(media_dir, exist_ok=True)
os.chdir(lambdaw_dir)

module_path = Path("project.py")
if not module_path.exists():
    module_path.touch()

# Load user project module by path.
# See https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
# We need to do it this way instead of just modifying sys.path in order to
# deal with having multiple "project" modules - one per Reaper project.
spec = importlib.util.spec_from_file_location("project", module_path)
user_project_module = importlib.util.module_from_spec(spec)
sys.modules["project"] = user_project_module
spec.loader.exec_module(user_project_module)
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
            # Expression item: may need evaluation
            snippets[take.id] = (var_name, expression, track_index, item_index, take)
            # reapy.print(f"SCAN: set {var_name} to {namespace[var_name]}")
    return snippets

snippets = scan_items()
project = reapy.Project()

counter = 0

CYCLE_LENGTH = project.time_signature[1] / project.time_signature[0] * 60  # seconds

# track -> take
next_cycle_items = {}

def is_expression_name(name):
    before, *after = name.split("=", 1)
    return after and (before == "" or before.isidentifier())

def execute(pending):
    global counter, snippets, project, next_cycle_items
    if not (pending or counter > 3):
        # Don't check for updates every time.
        counter += 1
        return
    counter = 0

    # Check for expressions in track names (livecoding mode)
    # TODO: Extract to separate function
    new_cycle_items = set()
    if project.is_recording:
        for track in project.tracks:
            if is_expression_name(track.name):
                if track.id in next_cycle_items and next_cycle_items[track.id].name != track.name:
                    take = next_cycle_items[track.id]
                    reapy.RPR.GetSetMediaItemTakeInfo_String(take.id, "P_NAME", track.name, True)
                    next_cycle_items[track.id] = take
                next_cycle_start = (project.play_position // CYCLE_LENGTH + 1) * CYCLE_LENGTH
                next_cycle_end = next_cycle_start + CYCLE_LENGTH
                for item in track.items:
                    if item.position < next_cycle_end and item.position + item.length > next_cycle_start:
                        break  # found an item there already
                else:
                    item = track.add_item(next_cycle_start, next_cycle_end)
                    # Visually indicate that next cycle is pending using item lock
                    item.set_info_value("C_LOCK", 1)
                    take = item.add_take()
                    reapy.RPR.GetSetMediaItemTakeInfo_String(take.id, "P_NAME", track.name, True)
                    old_take = next_cycle_items.get(track.id, None)
                    if old_take:
                        old_take.item.set_info_value("C_LOCK", 0)
                    next_cycle_items[track.id] = take
                    new_cycle_items.add(take.id)
    else:
        for take in next_cycle_items.values():
            take.item.delete()
        next_cycle_items = {}
        reapy.update_arrange()

    old_snippets = snippets
    snippets = scan_items()
    # TODO: Only convert *last* copy with name.
    for id, (var_name, expression, track_index, item_index, take) in snippets.items():
        # Avoid reading in items newly-generated from tracks, which are empty.
        if id not in new_cycle_items:
            namespace[var_name] = input_converter(take)

    changed = set()
    for key, value in snippets.items():
        if key not in old_snippets or old_snippets[key][1] != value[1]:
            changed.add(key)

    # Check for new/updated expressions in take names
    # reapy.print("TICK")
    if changed or pending:
        # reapy.print("changed:", {id: snippets[id][0] for id in changed})
        filter = {
            "eval_all": lambda _: True,
            "eval_selected": lambda take: take.item.is_selected or take.id in changed,
            "": lambda take: take.id in changed,
        }[pending]
        eval_takes(v for v in snippets.values() if filter(v[-1]))
