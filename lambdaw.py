import array
import collections
import importlib
import itertools
import numbers
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import wave

import reapy

SAMPLE_RATE = 48000

def generate_wave(path, it):
    # NOTE: Avoiding numpy due to segfault on reload: https://github.com/numpy/numpy/issues/11925
    wav = wave.open(path, "w")
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(SAMPLE_RATE)
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

def peek(iterable, default=None):
    it = iter(iterable)
    try:
        first = next(it)
    except StopIteration:
        return (default, ())
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
    if isinstance(output, collections.abc.Iterable):
        first, peeked_output = peek(output)
        if isinstance(first, dict):
            # MIDI notes (TODO: use dedicated type)
            if not take.is_midi:
                create_midi_source(take)
            for note in peeked_output:
                take.add_note(**convert_note(note))
            return False
        elif isinstance(first, numbers.Number):
            # audio samples
            path = os.path.join(audio_dir, f"track{track_index}_item{item_index}_{time.monotonic_ns()}.wav")
            generate_wave(path, itertools.islice(peeked_output, int(take.item.length * SAMPLE_RATE)))

            source = reapy.RPR.PCM_Source_CreateFromFile(os.path.join(lambdaw_dir, path))
            old_source = take.source
            reapy.RPR.SetMediaItemTake_Source(take.id, source)
            if Path(old_source.filename).is_relative_to(audio_dir):
                reapy.RPR.PCM_Source_Destroy(old_source.id)
            return True
    # For anything else, just put the repr in the item note.
    reapy.RPR.GetSetMediaItemInfo_String(take.item.id, "P_NOTES", repr(output), True)
    return False
        

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
audio_dir = os.path.abspath(os.path.join(lambdaw_dir, "audio"))

# Make directory for generated audio clips
os.makedirs(audio_dir, exist_ok=True)
os.chdir(lambdaw_dir)

module_path = Path("project.py")
if not module_path.exists():
    module_path.touch()

import importlib.abc

# Load user project module by path.
# See https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
# We need to do it this way instead of just modifying sys.path in order to
# deal with having multiple "project" modules - one per Reaper project.
# Switched to `sys.meta_path` after running into this issue:
# https://stackoverflow.com/questions/62052359/modulespec-not-found-during-reload-for-programmatically-imported-file-in-differe
class ModuleFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "project":
            return importlib.util.spec_from_file_location("project", module_path)

sys.meta_path.append(ModuleFinder())

if "project" in sys.modules:
    if module_path.samefile(sys.modules["project"].__file__):
        # reapy.print("reloading")
        importlib.reload(sys.modules["project"])
    else:
        # reapy.print("clearing previous project module", sys.modules["project"].__file__)
        del sys.modules["project"]
# else:
#     reapy.print("loading for the first time", lambdaw_dir)
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
        }.get(pending, lambda take: take.id in changed)
        eval_takes(v for v in snippets.values() if filter(v[-1]))

    if pending == "edit_expression":
        edit_expression()


# Experimental ImGui work
sys.path.append(reapy.get_resource_path() + "/Scripts/ReaTeam Extensions/API")
from imgui_python import *

module_source = open(module_path).read()

import io
from contextlib import redirect_stdout, redirect_stderr

try:
    history
except NameError:
    history = []

scroll_to_bottom = False

from code import InteractiveInterpreter
interp = InteractiveInterpreter(namespace)

COLORS = {
    "input": 0xFFCC99FF,
    "output": 0x6699FFFF, # 0xFFFFFFFF,
    "error": 0xFF6666FF,
}

# See console demo from https://github.com/cfillion/reaimgui/blob/v0.8.6.1/examples/demo.lua
# TODO: consider some fancy stuff for auto-reloading/upgrading instances of classes
class Console:
    def __init__(self):
        self.history = [""]
        self.history_pos = 0
        # Unfortunately, can't pass a Python callback into ReaImGui functions... so this bit is written in EEL.
        self.callback = ImGui_CreateFunctionFromEEL("""
EventFlag == InputTextFlags_CallbackHistory ? (
    prev_history_pos = HistoryPos;
    history_line = #;
    EventKey == Key_UpArrow && HistoryPos > 0 ? (
        HistoryPos -= 1;
        strcpy(history_line, #HistoryPrev);
    );
    EventKey == Key_DownArrow && HistoryPos < HistorySize - 1 ? (
        HistoryPos += 1;
        strcpy(history_line, #HistoryNext);
    );
    prev_history_pos != HistoryPos ? (
        InputTextCallback_DeleteChars(0, strlen(#Buf));
        InputTextCallback_InsertChars(0, history_line);
    );
);
""")
        flags = [
            'InputTextFlags_CallbackHistory',
            'Key_UpArrow', 'Key_DownArrow',
        ]
        for flag in flags:
            ImGui_Function_SetValue(self.callback, flag, globals()["ImGui_" + flag]())

    def pre_callback(self):
        ImGui_Function_SetValue(self.callback, 'HistoryPos', self.history_pos)
        ImGui_Function_SetValue(self.callback, 'HistorySize', len(self.history))
        ImGui_Function_SetValue_String(self.callback, '#HistoryPrev', self.history[self.history_pos == 0 and len(self.history) - 1 or self.history_pos - 1] if self.history else '')
        ImGui_Function_SetValue_String(self.callback, '#HistoryNext', self.history[self.history_pos + 1] if self.history_pos + 1 < len(self.history) else '')

    def post_callback(self):
        self.history_pos = int(ImGui_Function_GetValue(self.callback, 'HistoryPos'))

    def exec(self, command):
        self.history[-1] = command
        self.history.append("")
        self.history_pos = len(self.history) - 1
    
    def draw(self, ctx, label):
        self.pre_callback()
        sent, contents = ImGui_InputText(ctx, label, input_string, ImGui_InputTextFlags_CallbackHistory() | ImGui_InputTextFlags_EnterReturnsTrue(), self.callback)
        self.post_callback()
        if self.history_pos == len(self.history) - 1:
            # Save edits to latest line (so user can visit history without losing in-progress command).
            # If we wanted to make this more like readline, we'd do this with all the history while also saving the original commands (to be restored after executing).
            self.history[self.history_pos] = contents
        return sent, contents

try:
    process
except NameError:
    process = None

def get_process_status():
    if process is None:
        return "not started"
    process.poll()
    if process.returncode is None:
        return "alive"
    else:
        return f"dead ({process.returncode})"

import queue
q = queue.Queue()
def read_stdout():
    # reapy.print("stdout started")
    for line in process.stdout:
        # reapy.print("stdout", line)
        q.put(("output", line.decode("utf8")))

def read_stderr():
    # reapy.print("stderr started")
    for line in process.stderr:
        # reapy.print("stderr", line)
        q.put(("error", line.decode("utf8")))

import threading

def loop():
    global input_string, module_source, scroll_to_bottom, console, history, process, threads
    visible, open = ImGui_Begin(ctx, "LambDAW Editor + REPL", True)
    if visible:
        try:
            ImGui_Text(ctx, "subprocess status: " + get_process_status())
            ImGui_SameLine(ctx)
            if ImGui_Button(ctx, "start subprocess"):
                reapy.print("bang")
                process = subprocess.Popen(["python", "-i"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                threads = [threading.Thread(target=t) for t in (read_stdout, read_stderr)]
                for thread in threads: thread.start()

            ImGui_PushItemWidth(ctx, -1)
            _, module_source = ImGui_InputTextMultiline(ctx, "##module_source", module_source, 0, 200, ImGui_InputTextFlags_AllowTabInput())
            ImGui_PopItemWidth(ctx)

            while True:
                try:
                    history.append(q.get_nowait())
                    scroll_to_bottom = True
                except queue.Empty:
                    break

            if ImGui_BeginChild(ctx, 'ScrollingRegion', 0, -20, False, ImGui_WindowFlags_HorizontalScrollbar()):
                for (type, content) in history:
                    ImGui_PushStyleColor(ctx, ImGui_Col_Text(), COLORS[type])
                    if type == "input": content = ">>> " + content
                    ImGui_Text(ctx, content)
                    ImGui_PopStyleColor(ctx)
                if scroll_to_bottom:
                    ImGui_SetScrollHereY(ctx, 1.0)
                    scroll_to_bottom = False
                ImGui_EndChild(ctx)
            ImGui_Text(ctx, ">>>")
            ImGui_SameLine(ctx)
            ImGui_PushItemWidth(ctx, -1)
            sent, input_string = console.draw(ctx, "##code")
            ImGui_PopItemWidth(ctx)
            if sent:
                if process:
                    process.stdin.write((input_string + "\n").encode("utf8"))
                    process.stdin.flush()
                # with io.StringIO() as outbuf, io.StringIO() as errbuf, redirect_stdout(outbuf), redirect_stderr(errbuf):
                #     interp.runsource(input_string)
                #     output_string = outbuf.getvalue()
                #     error_string = errbuf.getvalue()
                # console.exec(input_string)
                history.append(("input", input_string))
                # if output_string: history.append(("output", output_string))
                # if error_string: history.append(("error", error_string))
                input_string = ""
                ImGui_SetKeyboardFocusHere(ctx, -1) # re-focus text input
                scroll_to_bottom = True
        finally:
            ImGui_End(ctx)
    if open:
        reapy.defer(loop)
    
    overlay()



# Overlay for expression input
expression_input = ""
show_expression_editor = False

def edit_expression():
    global show_expression_editor
    show_expression_editor = True

def overlay():
    global show_expression_editor
    if not show_expression_editor: return

    window_flags = (ImGui_WindowFlags_NoCollapse()       |
                    ImGui_WindowFlags_NoDocking()          |
                    ImGui_WindowFlags_AlwaysAutoResize()   |
                    ImGui_WindowFlags_NoSavedSettings())

    # Center window
    center_x, center_y = ImGui_Viewport_GetCenter(ImGui_GetMainViewport(ctx))
    ImGui_SetNextWindowPos(ctx, center_x, center_y, ImGui_Cond_Always(), 0.5, 0.5)
    # window_flags = window_flags | ImGui_WindowFlags_NoMove()

    ImGui_SetNextWindowBgAlpha(ctx, 0.6) # Translucent background

    rv, open = ImGui_Begin(ctx, 'Enter name/expression', True, window_flags)
    if not rv: return open

    ImGui_Text(ctx, "ex: `=osc(440)`, `foo=bar(baz)`")

    global expression_input
    if ImGui_IsWindowAppearing(ctx):
        ImGui_SetKeyboardFocusHere(ctx)
    done, expression_input = ImGui_InputText(ctx, "##expression", expression_input, ImGui_InputTextFlags_EnterReturnsTrue())
    if ImGui_IsKeyPressed(ctx, ImGui_Key_Escape()):
        show_expression_editor = False
    if done:
        # TODO: if no item is selected, create a new item with the given expression. probably should have some max duration in case of infinite streams.
        reapy.RPR.GetSetMediaItemTakeInfo_String(project.get_selected_item(0).active_take.id, "P_NAME", expression_input, True)
        expression_input = ""
        show_expression_editor = False

    ImGui_End(ctx)



# Don't restart ImGui context on reload
try:
    ctx
except NameError:
    input_string = ""
    ctx = ImGui_CreateContext("LambDAW")
    console = Console()
    loop()
