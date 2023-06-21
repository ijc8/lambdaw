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
from contextlib import redirect_stdout

try:
    history
except NameError:
    history = ""

scroll_to_bottom = False

def loop():
    global input_string, output_string, module_source, history, scroll_to_bottom
    visible, open = ImGui_Begin(ctx, 'My window', True)
    if visible:
        try:
            _, module_source = ImGui_InputTextMultiline(ctx, "##module_source", module_source, 0, 0) #, 0, 0, ImGui_InputTextFlags_AllowTabInput())

            if ImGui_BeginChild(ctx, 'ScrollingRegion', 0, -20, False, ImGui_WindowFlags_HorizontalScrollbar()):
                ImGui_Text(ctx, history)
                if scroll_to_bottom:
                    ImGui_SetScrollHereY(ctx, 1.0)
                    scroll_to_bottom = False
                ImGui_EndChild(ctx)
            ImGui_Text(ctx, ">>>")
            ImGui_SameLine(ctx)
            # h = ImGui_CalcTextSize(ctx, input_string)[1] + ImGui_StyleVar_FramePadding()
            # h = ImGui_GetTextLineHeightWithSpacing(ctx) * input_string.count('\n')
            _, input_string = ImGui_InputText(ctx, "##code", input_string) #, 0, 0, ImGui_InputTextFlags_AllowTabInput())
            # if ImGui_GetKeyMods(ctx) & ImGui_Mod_Shift() and ImGui_IsKeyPressed(ctx, ImGui_Key_Enter()):
            if ImGui_IsKeyPressed(ctx, ImGui_Key_Enter()):
                try:
                    reapy.print(repr(input_string))
                    with io.StringIO() as buf, redirect_stdout(buf):
                        exec(compile(input_string, "<repl>", "single"), globals())
                        output_string = buf.getvalue()
                except Exception as e:
                    output_string = repr(e)
                history += ">>> " + input_string + "\n" + output_string
                input_string = ""
                ImGui_SetKeyboardFocusHere(ctx, -1) # re-focus text input
                scroll_to_bottom = True
        finally:
            ImGui_End(ctx)
    if open:
        reapy.defer(loop)

def gui_test():
    global ctx, input_string, output_string
    input_string = ""
    output_string = "<output>"
    ctx = ImGui_CreateContext('My script')
