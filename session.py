import ctypes
import importlib
import traceback

import reapy

import lambdaw

reapy.print("started lambdaw session")

# HACK: Crazy workaround for issue with REAPER's Python support.
# Every time REAPER runs a Python script, ctypes is reimported and resets its pointer type cache.
# This affects *all* instances of Python and can screw up libraries that depend on ctypes
# by causing spurious ctypes ArgumentErrors (due to mismatch between pre- and post-reset pointer types).
# To workaround this, we restore *our* ctypes cache whenever we re-enter this script (and save it when we defer).
ctype_backup = ctypes._pointer_type_cache.copy()

def run_loop():
    global ctype_backup
    ctypes._pointer_type_cache.update(ctype_backup)

    pending = reapy.get_ext_state("lambdaw", "pending")
    try:
        if pending == "reload":
            importlib.reload(lambdaw)
            reapy.print("Reloaded lambdaw")
        else:
            lambdaw.execute(pending)
    except:
        reapy.show_message_box(traceback.format_exc(), "lambdaw exception")

    if pending:
        reapy.delete_ext_state("lambdaw", "pending")
    ctype_backup.update(ctypes._pointer_type_cache)
    reapy.defer(run_loop)

run_loop()
