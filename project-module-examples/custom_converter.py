import lambdaw
from aleatora import *

# Here, we override LambDAW's default behavior to
# control how it converts Python values into DAW items.
def custom_convert_output(output, *args):
    # `output` may be a (potentially endless) iterable.
    # So, we peek at the first item in order to determine the type.
    first, output = lambdaw.peek(output)
    if isinstance(first, tuple):
        output = midi.events_to_notes(output)
    # Fallback to default converter for any other type.
    return lambdaw.convert_output(output, *args)

lambdaw.register_converters(output=custom_convert_output)
