import ctypes
import importlib
import traceback

import reapy

lambdaw = None
try:
    import lambdaw
    needs_load = False
except:
    reapy.show_message_box(traceback.format_exc(), "lambdaw exception")
    needs_load = True

reapy.delete_ext_state("lambdaw", "pending")

# HACK: Crazy workaround for issue with REAPER's Python support.
# Every time REAPER runs a Python script, ctypes is reimported and resets its pointer type cache.
# This affects *all* instances of Python and can screw up libraries that depend on ctypes
# by causing spurious ctypes ArgumentErrors (due to mismatch between pre- and post-reset pointer types).
# To workaround this, we restore *our* ctypes cache whenever we re-enter this script (and save it when we defer).
ctype_backup = ctypes._pointer_type_cache.copy()

def run_loop():
    global lambdaw, needs_load, ctype_backup
    ctypes._pointer_type_cache.update(ctype_backup)

    pending = reapy.get_ext_state("lambdaw", "pending")
    try:
        if pending == "reload" or (pending and not lambdaw):
            needs_load = True
        if needs_load:
            if lambdaw is None:
                import lambdaw
            else:
                importlib.reload(lambdaw)
            reapy.show_message_box("Reloaded module.", "lambdaw", "ok")
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
