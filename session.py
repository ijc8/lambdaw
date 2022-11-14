import importlib
import traceback

import reapy

import lambdaw

reapy.print("started lambdaw session")

def run_loop():
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
    reapy.defer(run_loop)

run_loop()
