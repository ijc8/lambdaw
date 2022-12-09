import reapy

last_project, last_play_position = None, None

def run_loop():
    global last_project, last_play_position
    p = reapy.Project()
    if p.time_selection.is_looping:
        play_position = p.play_position
        if last_project == p and last_play_position < p.time_selection.end and play_position < last_play_position:
            reapy.print("Looped!")
            if p.selected_items:
                # Tranpose all notes up one semitone every loop.
                take = p.selected_items[0].active_take
                new_notes = []
                while take.n_notes:
                    new_notes.append(take.notes[0].infos)
                    take.notes[0].delete()
                take_start = take.item.position - take.start_offset
                for note in new_notes:
                    reapy.print(note)
                    note["start"] -= take_start
                    note["end"] -= take_start
                    note["pitch"] += 1
                    reapy.print(note)
                    take.add_note(**note, sort=False)

        last_project, last_play_position = p, play_position
    else:
        last_project, last_play_position = None, None

    reapy.defer(run_loop)

run_loop()
