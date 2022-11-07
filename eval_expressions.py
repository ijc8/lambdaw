import reapy

p = reapy.Project()

def transpose(notes, amount):
    return [{**note, "pitch": note["pitch"] + amount} for note in notes]

with reapy.undo_block("Evaluate all clips"):
    namespace = {"transpose": transpose}
    to_derive = []
    for track in p.tracks:
        for item in track.items:
            take = item.active_take
            if take.name.startswith('='):
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
