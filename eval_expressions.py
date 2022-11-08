import reapy
import random
from typing import List

p = reapy.Project()

def note(start, dur, pitch, **args):
    return {"start": start, "end": start + dur, "pitch": pitch, **args}

def transpose(notes, amount):
    return [{**note, "pitch": note["pitch"] + amount} for note in notes]

namespace = {"note": note, "transpose": transpose, **{key: getattr(random, key) for key in random.__all__}}
to_derive: List[reapy.Take] = []

with reapy.undo_block("Evaluate all clips"):
    for track in p.tracks:
        for item in track.items:
            take = item.active_take
            if take.name.startswith("="):
                # Derived clip
                to_derive.append(take)
            else:
                namespace[take.name] = [note.infos for note in take.notes]
    for take in to_derive:
        notes = eval(take.name[1:], namespace)
        # Clear current notes
        while take.n_notes:
            take.notes[0].delete()
        for note in notes:
            take.add_note(**note)
