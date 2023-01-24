import ctypes
import importlib
import time
import traceback

import reapy

lambdaw = None
project_info = None
needs_load = True
reapy.delete_ext_state("lambdaw", "pending")

# HACK: Crazy workaround for issue with REAPER's Python support.
# Every time REAPER runs a Python script, ctypes is reimported and resets its pointer type cache.
# This affects *all* instances of Python and can screw up libraries that depend on ctypes
# by causing spurious ctypes ArgumentErrors (due to mismatch between pre- and post-reset pointer types).
# To workaround this, we restore *our* ctypes cache whenever we re-enter this script (and save it when we defer).
ctype_backup = ctypes._pointer_type_cache.copy()

def run_loop():
    global lambdaw, project_info, needs_load, ctype_backup
    ctypes._pointer_type_cache.update(ctype_backup)

    pending = reapy.get_ext_state("lambdaw", "pending")
    current_project = reapy.Project()
    # Try to detect when user switches projects.
    # (ID only changes on tab switch, not when the user opens a different project in the current tab.)
    current_project_info = (current_project.id, current_project.name, current_project.path)
    if project_info != current_project_info:
        project_info = current_project_info
        needs_load = True  # reload on project switch
    elif pending == "reload" or (pending and not lambdaw):
        needs_load = True
    try:
        if needs_load:
            start = time.time()
            if lambdaw is None:
                import lambdaw
            else:
                importlib.reload(lambdaw)
            reapy.RPR.Help_Set(f"lambdaw: loaded module in {time.time() - start:.3f} seconds", False)
            needs_load = False
        if pending != "reload" and lambdaw:
            lambdaw.execute(pending)
    except:
        reapy.show_message_box(traceback.format_exc(), "lambdaw exception")

    if pending:
        reapy.delete_ext_state("lambdaw", "pending")
    ctype_backup.update(ctypes._pointer_type_cache)
    reapy.defer(run_loop)

run_loop()
