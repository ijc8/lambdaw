import reapy
import os
import subprocess

path = os.path.join(reapy.Project().path, "lambdaw", "project.py")
subprocess.run(["code", "-n", path])
