import py5
import math
import os
import random
import sys

offset_x = 0
def moving_square(sketch):
    global offset_x
    offset_x += (random.random() - 0.5)
    t = sketch.frame_count / 10
    sketch.square(math.cos(t)*50+100+offset_x, math.sin(t)*50+100, 10)

def colorful_squares(py5):
    py5.rect_mode(py5.CENTER)
    py5.fill(py5.random(255), py5.random(255), py5.random(255))
    py5.rect(py5.random(py5.width), py5.random(py5.height), 10, 10)


def spinning_cube(py5):
    py5.background(0)
    py5.translate(py5.width / 2, py5.height / 2, -py5.width / 2)
    py5.no_stroke()
    py5.stroke_weight(4)
    py5.fill(192, 255, 192)
    py5.point_light(255, 255, 255, 0, -500, 500)
    py5.rotate_y(py5.frame_count/30.0)
    py5.box(300, 300, 300)

demos = {
    "moving-square": (moving_square, py5.HIDDEN),
    "colorful-squares": (colorful_squares, py5.P2D),
    "spinning-cube": (spinning_cube, py5.P3D),
}

draw, renderer = demos[sys.argv[1]]

for i, frame in enumerate(py5.render_frame_sequence(draw, 1280, 720, limit=200, renderer=renderer)):
    frame.save(os.path.join(sys.argv[2], f"frame_{i:04}.png"))
