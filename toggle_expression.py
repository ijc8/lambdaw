import re
import reapy

project = reapy.Project()

expr_regex = re.compile("(.*?)([=≠])(.*)")

def toggle_expression(expr):
    if match := expr_regex.match(expr):
        name, equal, expression = match.groups()
        return name + "=≠"[equal == "="] + expression

if project.n_selected_items:
    for item in project.selected_items:
        take = item.active_take
        if new_name := toggle_expression(take.name):
            reapy.RPR.GetSetMediaItemTakeInfo_String(take.id, "P_NAME", new_name, True)
else:
    for track in project.selected_tracks:
        if new_name := toggle_expression(track.name):
            track.name = new_name
