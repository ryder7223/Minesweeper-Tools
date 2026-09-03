"""
Works on Windows XP Minesweeper version 5.1.2600.

If you use another version, you will need to find the offsets
used by that version.
"""

import importlib
import os
import subprocess
import sys
import time
from typing import Any

REQUIRED_MODULES = ("pymem",)

PROCESS_NAME = "winmine.exe"

BASE_OFFSET = 0x5361
WIDTH_OFFSET = 0x5334
HEIGHT_OFFSET = 0x5338
END_GAME_STATE = 0x5160
DIFFICULTY = 0x56A0
TIMER = 0x579C

DOWN_VALUE = 0
UNKNOWN_VALUE = 15
BOMB_VALUE = 143

POLL_INTERVAL = 0.0


def installMissingModules(modules: tuple[str, ...]) -> None:
    """Install modules that are not already available."""
    try:
        importlib.import_module("pip")
    except ImportError:
        print("pip is not installed. Installing...")
        subprocess.check_call(
            [sys.executable, "-m", "ensurepip", "--upgrade"]
        )

    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"{module} is not installed. Installing...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", module]
            )


installMissingModules(REQUIRED_MODULES)

import pymem
import pymem.process


def readBoard(
    pm: pymem.Pymem,
    moduleBase: int,
    rowCount: int,
    colCount: int
) -> list[list[int]]:
    """Read the current Minesweeper board from memory."""
    return [
        list(
            pm.read_bytes(
                moduleBase + BASE_OFFSET + row * 0x20,
                colCount
            )
        )
        for row in range(rowCount)
    ]


def getBoardSize(pm: pymem.Pymem, moduleBase: int) -> tuple[int, int]:
    """Return the current board width and height."""
    width = pm.read_int(moduleBase + WIDTH_OFFSET)
    height = pm.read_int(moduleBase + HEIGHT_OFFSET)
    if isinstance(width, int) and isinstance(height, int):
        return width, height
    raise RuntimeError("Could not read board size.")


def boardHasStarted(pm, board: list[list[int]]) -> bool:
    """Return True if the board contains a revealed cell."""
    timer = readFromOffset(pm, TIMER)
    gameState = readFromOffset(pm, END_GAME_STATE)
    return not untouched(board) and gameState == 0 and timer > 0


def getModuleBase(pm: pymem.Pymem) -> Any:
    module = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)

    if module is None:
        raise RuntimeError("Could not find process module")

    return module.lpBaseOfDll


def readFromOffset(pm, offset: int) -> Any:
    moduleBase = getModuleBase(pm)
    return pm.read_int(moduleBase + offset)


def getBoardValues(pm: pymem.Pymem) -> list[list[int]]:
    """Return the current Minesweeper board values."""
    moduleBase = getModuleBase(pm)
    width, height = getBoardSize(pm, moduleBase)

    return readBoard(
        pm,
        moduleBase,
        height,
        width
    )


def waitForGameStart(pm: pymem.Pymem) -> float:
    """
    Wait until the board contains a value other than 15 or 143.

    The board size is deliberately ignored.
    """

    while True:
        board = getBoardValues(pm)

        if boardHasStarted(pm, board):
            startTime = time.perf_counter()
            diff = readFromOffset(pm, DIFFICULTY)
            width = readFromOffset(pm, WIDTH_OFFSET)
            height = readFromOffset(pm, HEIGHT_OFFSET)
            mines = countInBoard(board, (143, 128))
            print("Difficulty: ", end="")
            match diff:
                case 0:
                    print("Beginner",end="")
                case 1:
                    print("Intermediate",end="")
                case 2:
                    print("Expert",end="")
                case 3:
                    print(f"Custom",end="")
            print(f" [{width}x{height} | {mines}]")

            return startTime

        time.sleep(POLL_INTERVAL)


def waitForGameEnd(pm: pymem.Pymem) -> int | Any:
    """
    Wait until Minesweeper reports that the game has ended.
    """
    while True:
        board = getBoardValues(pm)
        gameState = readFromOffset(pm, END_GAME_STATE)
        if gameState != 0 or untouched(board):
            return gameState

        time.sleep(POLL_INTERVAL)


def waitForGameReset(pm: pymem.Pymem) -> None:
    """
    Wait for the ended game to be reset.

    END_GAME_STATE == 0 means the board has been reset and no
    new game has started yet.
    """
    while True:
        board = getBoardValues(pm)
        gameState = readFromOffset(pm, END_GAME_STATE)
        if gameState == 0 and untouched(board):
            return

        time.sleep(POLL_INTERVAL)


def untouched(values: list[list[int]]) -> bool:
    return all(val in (UNKNOWN_VALUE, BOMB_VALUE, DOWN_VALUE) for _ in values for val in _)

def countInBoard(values: list[list[int]], numbers: tuple[int]) -> bool:
    return sum(val in numbers for _ in values for val in _)

def gameLoop(pm: pymem.Pymem) -> None:
    """Monitor Minesweeper games indefinitely."""
    while True:
        board = getBoardValues(pm)
        if not untouched(board):
            continue
        # State 1: wait for a board containing a revealed cell.
        startTime = waitForGameStart(pm)

        # State 2: game is active; only END_GAME_STATE can end it.
        gameState = waitForGameEnd(pm)

        elapsed = time.perf_counter() - startTime

        match gameState:
            case 2:
                print("[Loss] ", end="")
            case 3: 
                print("[Win] ", end="")
            case 0:
                print("[Reset] ", end="")
        print(f"Time elapsed: {elapsed:.3f}")
        print("-" * 21)

        # State 3: game has ended. Wait until the smiley/reset
        # operation puts END_GAME_STATE back to 0.
        waitForGameReset(pm)


def main() -> None:
    os.system("cls" if os.name == "nt" else "clear")

    try:
        pm = pymem.Pymem(PROCESS_NAME)
        gameLoop(pm)

    except pymem.exception.ProcessNotFound:
        print(f"Error: Process '{PROCESS_NAME}' not found.")
    except Exception as error:
        print(f"Unexpected error occurred:\n{error}")


if __name__ == "__main__":
    main()
