# Lambda + DAW = LambDAW[^1]

Make generative music, hack the timeline, livecode the DAW.

## What is this?

LambDAW is a REAPER extension that lets you write code that generates media right in the timeline, where it happily co-exists with audio and MIDI items.
This code takes the form of Python expressions, which are associated with the items they generate (_expression items_), and can refer to other items in the timeline to transform them.

If this seems a bit abstract, think of how spreadsheets let you mix formulas with data: a cell can contain either, and formulas can refer to other cells, allowing you to express _relationships_ between different pieces of information. LambDAW is kind of like that, but for the digital audio workstation.

![Screenshot of LambDAW showing expression items mixed with audio and MIDI items](https://user-images.githubusercontent.com/99575/209230218-d7150bb7-dc65-434a-95a6-7b01804be813.png)

## What's the project status?

:warning: LambDAW is under heavy development. :warning:

In the future, we may release an extension compatible with [ReaPack](https://reapack.com/).
Until then, you can try it by cloning the repo, running `session.py` as a script in REAPER, and tweaking your setup (keybindings and theme) to make it convenient to use. You can also find a few basic examples of project modules in `project-module-examples/` which might be helpful for getting started.

If you are interested it trying LambDAW, feel free to contact [the author](https://ijc8.me).

[^1]: Any substrings related to lambs or other young ovines are purely coincidental, and no animals were harmed in the making of this software.
