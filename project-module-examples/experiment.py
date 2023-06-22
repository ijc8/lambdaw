from aleatora import *

import reapy

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
        project = reapy.Project()
        yield {"pitch": note_to_pitch(event.value["note"]), "start": float(project.beats_to_time(event.part.begin * project.time_signature[1])), "end": float(project.beats_to_time(event.part.end * project.time_signature[1]))}

from reapy import RPR

import sys
sys.path.append(reapy.get_resource_path() + "/Scripts/ReaTeam Extensions/API")
from imgui_python import *

# check if state survives reloads
try:
    bar += 1
except NameError:
    bar = 0
reapy.print(bar)

module_source = open(__file__).read()

import io
from contextlib import redirect_stdout, redirect_stderr

try:
    history
except NameError:
    history = []

scroll_to_bottom = False

from code import InteractiveInterpreter
interp = InteractiveInterpreter(globals())

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
        changed, contents = ImGui_InputText(ctx, label, input_string, ImGui_InputTextFlags_CallbackHistory(), self.callback)
        self.post_callback()
        if self.history_pos == len(self.history) - 1:
            # Save edits to latest line (so user can visit history without losing in-progress command).
            # If we wanted to make this more like readline, we'd do this with all the history while also saving the original commands (to be restored after executing).
            self.history[self.history_pos] = contents
        return changed, contents

def loop():
    global input_string, module_source, scroll_to_bottom, console, history
    visible, open = ImGui_Begin(ctx, 'My window', True)
    if visible:
        try:
            ImGui_PushItemWidth(ctx, -1)
            _, module_source = ImGui_InputTextMultiline(ctx, "##module_source", module_source, 0, 0, ImGui_InputTextFlags_AllowTabInput())
            ImGui_PopItemWidth(ctx)

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
            _, input_string = console.draw(ctx, "##code")
            ImGui_PopItemWidth(ctx)
            if ImGui_IsKeyPressed(ctx, ImGui_Key_Enter()):
                with io.StringIO() as outbuf, io.StringIO() as errbuf, redirect_stdout(outbuf), redirect_stderr(errbuf):
                    interp.runsource(input_string)
                    output_string = outbuf.getvalue()
                    error_string = errbuf.getvalue()
                console.exec(input_string)
                history.append(("input", input_string))
                if output_string: history.append(("output", output_string))
                if error_string: history.append(("error", error_string))
                input_string = ""
                ImGui_SetKeyboardFocusHere(ctx, -1) # re-focus text input
                scroll_to_bottom = True
        finally:
            ImGui_End(ctx)
    if open:
        reapy.defer(loop)

def gui_test():
    global ctx, input_string, console
    input_string = ""
    ctx = ImGui_CreateContext('My script')
    console = Console()
