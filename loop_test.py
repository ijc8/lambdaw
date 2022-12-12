import reapy

last_project, last_play_position = None, None

next_take = 1

def run_loop():
    global last_project, last_play_position, next_take
    p = reapy.Project()
    if p.time_selection.is_looping:
        play_position = p.play_position
        if last_project == p and last_play_position < p.time_selection.end and play_position < last_play_position:
            reapy.print("Looped!")
            p.selected_items[0].takes[next_take].make_active_take()
            next_take = 1 - next_take

        last_project, last_play_position = p, play_position
    else:
        last_project, last_play_position = None, None

    reapy.defer(run_loop)

run_loop()
