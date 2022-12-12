import reapy

project = reapy.Project()

if project.n_selected_items:
    for item in project.selected_items:
        # TODO: update for names with LHS, as in "foo=bar".
        take = item.active_take
        if take.name.startswith("="):
            reapy.RPR.GetSetMediaItemTakeInfo_String(take.id, "P_NAME", "≠" + take.name[1:], True)
        elif take.name.startswith("≠"):
            reapy.RPR.GetSetMediaItemTakeInfo_String(take.id, "P_NAME", "=" + take.name[1:], True)
else:
    for track in project.selected_tracks:
        if track.name.startswith("="):
            track.name = "≠" + track.name[1:]
        elif track.name.startswith("≠"):
            track.name = "=" + track.name[1:]
