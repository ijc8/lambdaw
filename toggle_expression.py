import reapy

for item in reapy.Project().selected_items:
    take = item.active_take
    if take.name.startswith("="):
        reapy.RPR.GetSetMediaItemTakeInfo_String(take.id, "P_NAME", "≠" + take.name[1:], True)
    elif take.name.startswith("≠"):
        reapy.RPR.GetSetMediaItemTakeInfo_String(take.id, "P_NAME", "=" + take.name[1:], True)
