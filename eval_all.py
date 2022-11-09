from lambdaw import eval_takes, namespace
import reapy

with reapy.undo_block("Evaluate all clips"):
    eval_takes(False)
