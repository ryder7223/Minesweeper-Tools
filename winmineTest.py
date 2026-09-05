"""
Example usage of processTool
"""

import subprocess
import importlib
import sys

requiredModules = {
	"processTool": {
		"package": "processTool",
		"args": [
			"--index-url",
			"https://pypi.org/simple/",
			"--extra-index-url",
			"https://test.pypi.org/simple/"
		]
	}
}

def installMissingModules(modules):
    installedSomething = False
    for importName, moduleInfo in modules.items():
        try:
            importlib.import_module(importName)
            
        except ImportError:
            packageName = moduleInfo["package"]
            extraArgs = moduleInfo.get("args", [])
            print(f"{packageName} is not installed. Installing...")
            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                *extraArgs,
                packageName])
            installedSomething = True
    if installedSomething:
        subprocess.check_call([sys.executable] + sys.argv)
        sys.exit()

installMissingModules(requiredModules)

from processTool import Process
import os

ms = Process("winmine.exe")
start = 0x5361
WIDTH_OFFSET = 0x5334
HEIGHT_OFFSET = 0x5338

while True:
	width = ms.readUInt(ms.moduleBase + WIDTH_OFFSET)
	height = ms.readUInt(ms.moduleBase + HEIGHT_OFFSET)

	if height is None:
		raise RuntimeError("Failed")

	if width is None:
		raise RuntimeError("Failed")

	for i in range(height):
		row_bytes = ms.readBytes(ms.moduleBase + start + i * 0x20, width)
		if row_bytes is not None:
			rowConv = [1 if x == 143 else 0 for x in row_bytes]
			print(*rowConv)
	
	input()
	os.system("cls")