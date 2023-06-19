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

def gui_test():
    ctx = ImGui_CreateContext('My script')
    input_string = ""
    output_string = "<output>"
    def loop():
        nonlocal input_string, output_string
        visible, open = ImGui_Begin(ctx, 'My window', True)
        if visible:
            ImGui_Text(ctx, output_string)
            # changed, contents = ImGui_InputText(ctx, 'input text', input_string, None, ImGui_InputTextFlags_EnterReturnsTrue())
            ImGui_Text(ctx, ">>>")
            ImGui_SameLine(ctx)
            _, input_string = ImGui_InputText(ctx, "##code", input_string)
            if ImGui_IsKeyPressed(ctx, ImGui_Key_Enter()):
                try:
                    output_string = repr(eval(input_string))
                except Exception as e:
                    output_string = repr(e)
            ImGui_End(ctx)
        if open:
            reapy.defer(loop)

    reapy.defer(loop)
