from lambdaw import eval_takes
import reapy

with reapy.undo_block("Evaluate selected clips"):
    eval_takes(True)
