"""
Works on Windows XP Minesweeper version 5.1.2600.

If you use another version, you will need to find the offsets
used by that version.
"""

import importlib
import os
import random
import subprocess
import sys
import time
from collections import deque

REQUIRED_MODULES = ("pynput", "pymem")

PROCESS_NAME = "winmine.exe"

BASE_OFFSET = 0x5361
WIDTH_OFFSET = 0x5334
HEIGHT_OFFSET = 0x5338
CLICK_X_OFFSET = 0x5118
CLICK_Y_OFFSET = 0x511C
END_GAME_STATE = 0x5160
DIFFICULTY = 0x56A0

DOWN_VALUE = 0
UNKNOWN_VALUE = 15
BOMB_VALUE = 143

CELL_SIZE = 16
POLL_INTERVAL = 0.01

BOARD_ORIGIN = (0, 0)


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

from pynput.mouse import Button, Controller

import pymem
import pymem.process


mouse = Controller()
left = Button.left

NUMBER_VALUES = {
    value: value - 64
    for value in range(65, 74)
}


def getModuleBase(pm: pymem.Pymem) -> int:
    """Return the base address of the Minesweeper module."""
    module = pymem.process.module_from_name(
        pm.process_handle,
        PROCESS_NAME
    )

    if module is None:
        raise RuntimeError("Could not find process module")

    return module.lpBaseOfDll


def readFromOffset(pm: pymem.Pymem, offset: int) -> int:
    """Read a 32-bit integer from a Minesweeper memory offset."""
    moduleBase = getModuleBase(pm)
    return pm.read_int(moduleBase + offset)


def getBoardSize(pm: pymem.Pymem) -> tuple[int, int]:
    """Return the current board width and height."""
    moduleBase = getModuleBase(pm)

    width = pm.read_int(moduleBase + WIDTH_OFFSET)
    height = pm.read_int(moduleBase + HEIGHT_OFFSET)

    if not isinstance(width, int) or not isinstance(height, int):
        raise RuntimeError("Could not read board size.")

    return width, height


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


def getBoardValues(pm: pymem.Pymem) -> list[list[int]]:
    """Return the current Minesweeper board values."""
    moduleBase = getModuleBase(pm)
    width, height = getBoardSize(pm)

    return readBoard(
        pm,
        moduleBase,
        height,
        width
    )


def untouched(board: list[list[int]]) -> bool:
    """
    Return True if the board contains no revealed cells.

    Unopened, flagged and down cells are all considered untouched.
    """
    return all(
        cell in (UNKNOWN_VALUE, BOMB_VALUE, DOWN_VALUE)
        for row in board
        for cell in row
    )


def boardHasStarted(board: list[list[int]]) -> bool:
    """Return True if the board contains a revealed cell."""
    return not untouched(board)


def getNeighbours(
    x: int,
    y: int,
    width: int,
    height: int
) -> list[tuple[int, int]]:
    """Return all valid neighbouring coordinates."""
    return [
        (nx, ny)
        for nx in range(x - 1, x + 2)
        for ny in range(y - 1, y + 2)
        if (
            0 <= nx < width
            and 0 <= ny < height
            and (nx, ny) != (x, y)
        )
    ]


def findNumberCells(
    board: list[list[int]]
) -> dict[tuple[int, int], int]:
    """Return coordinates and values of all revealed number cells."""
    return {
        (x, y): NUMBER_VALUES[cell]
        for y, row in enumerate(board)
        for x, cell in enumerate(row)
        if cell in NUMBER_VALUES
    }


def deduceSafeCells(
    board: list[list[int]]
) -> set[tuple[int, int]]:
    """
    Find unopened cells that are known to be safe based on
    neighbouring numbers and flagged bombs.
    """
    height = len(board)
    width = len(board[0]) if height else 0

    safeCells: set[tuple[int, int]] = set()

    for (x, y), number in findNumberCells(board).items():
        neighbours = getNeighbours(
            x,
            y,
            width,
            height
        )

        hidden = [
            position
            for position in neighbours
            if board[position[1]][position[0]] == UNKNOWN_VALUE
        ]

        bombs = sum(
            board[ny][nx] == BOMB_VALUE
            for nx, ny in neighbours
        )

        if bombs == number:
            safeCells.update(hidden)

    return safeCells


def bfsPath(
    start: tuple[int, int],
    goal: tuple[int, int],
    width: int,
    height: int
) -> list[tuple[int, int]]:
    """Find the shortest path between two board coordinates."""
    if start == goal:
        return [start]

    queue = deque([start])
    previous: dict[
        tuple[int, int],
        tuple[int, int] | None
    ] = {start: None}

    directions = (
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
    )

    while queue:
        x, y = queue.popleft()

        for dx, dy in directions:
            nx = x + dx
            ny = y + dy
            position = (nx, ny)

            if (
                not 0 <= nx < width
                or not 0 <= ny < height
                or position in previous
            ):
                continue

            previous[position] = (x, y)

            if position == goal:
                path = []
                current = goal

                while current is not None:
                    path.append(current)
                    current = previous[current]

                path.reverse()
                return path

            queue.append(position)

    return []


def findRandomSafeGuess(
    board: list[list[int]]
) -> tuple[int, int] | None:
    """Choose a random unopened cell."""
    candidates = [
        (x, y)
        for y, row in enumerate(board)
        for x, cell in enumerate(row)
        if cell == UNKNOWN_VALUE
    ]

    return random.choice(candidates) if candidates else None


def clickCell(x: int, y: int) -> None:
    """Move the mouse to a board cell and left-click it."""
    screenX = BOARD_ORIGIN[0] + x * CELL_SIZE
    screenY = BOARD_ORIGIN[1] + y * CELL_SIZE

    mouse.position = (screenX, screenY)
    mouse.click(left)


def clickIfUnopened(
    pm: pymem.Pymem,
    x: int,
    y: int
) -> bool:
    """Click a cell only if it is currently unopened."""
    moduleBase = getModuleBase(pm)

    address = (
        moduleBase
        + BASE_OFFSET
        + y * 0x20
        + x
    )

    if pm.read_uchar(address) != UNKNOWN_VALUE:
        return False

    clickCell(x, y)
    return True


def waitForGameStart(pm: pymem.Pymem) -> float:
    """
    Wait until the board contains a value other than 15, 143 or 0.

    Board dimensions are deliberately ignored.
    """
    while True:
        board = getBoardValues(pm)

        if boardHasStarted(board):
            startTime = time.perf_counter()

            difficulty = readFromOffset(
                pm,
                DIFFICULTY
            )

            print("Difficulty: ", end="")

            match difficulty:
                case 0:
                    print("Beginner")
                case 1:
                    print("Intermediate")
                case 2:
                    print("Expert")
                case _:
                    print(f"Unknown ({difficulty})")

            print("Game started.")

            return startTime

        time.sleep(POLL_INTERVAL)


def waitForGameEnd(pm: pymem.Pymem) -> int:
    """
    Wait until Minesweeper reports that the game has ended.

    END_GAME_STATE is the only condition used to end an active game.
    """
    while True:
        gameState = readFromOffset(
            pm,
            END_GAME_STATE
        )

        if gameState != 0:
            return gameState

        time.sleep(POLL_INTERVAL)


def waitForGameReset(pm: pymem.Pymem) -> None:
    """
    Wait until the completed game has been reset.

    Both END_GAME_STATE == 0 and an untouched board are required.
    """
    while True:
        gameState = readFromOffset(
            pm,
            END_GAME_STATE
        )

        board = getBoardValues(pm)

        if gameState == 0 and untouched(board):
            return

        time.sleep(POLL_INTERVAL)


def fallbackExploreAll(
    pm: pymem.Pymem,
    startPosition: tuple[int, int]
) -> tuple[int, int]:
    """
    Click the nearest unopened cells until no unopened cells remain
    or the game ends.
    """
    currentPosition = startPosition

    while True:
        if readFromOffset(pm, END_GAME_STATE) != 0:
            return currentPosition

        board = getBoardValues(pm)

        if untouched(board):
            return currentPosition

        height = len(board)
        width = len(board[0]) if height else 0

        unclicked = [
            (x, y)
            for y, row in enumerate(board)
            for x, cell in enumerate(row)
            if cell == UNKNOWN_VALUE
        ]

        if not unclicked:
            return currentPosition

        bestPath: list[tuple[int, int]] | None = None

        for target in unclicked:
            path = bfsPath(
                currentPosition,
                target,
                width,
                height
            )

            if path and (
                bestPath is None
                or len(path) < len(bestPath)
            ):
                bestPath = path

        if bestPath is None:
            return currentPosition

        for x, y in bestPath[1:]:
            if readFromOffset(pm, END_GAME_STATE) != 0:
                return currentPosition

            if clickIfUnopened(pm, x, y):
                currentPosition = (x, y)
                time.sleep(POLL_INTERVAL)


def solveGame(
    pm: pymem.Pymem,
    startTime: float
) -> int:
    """
    Solve the active Minesweeper game.

    Returns the END_GAME_STATE value when the game ends.
    """
    board = getBoardValues(pm)

    if not board:
        return readFromOffset(pm, END_GAME_STATE)

    height = len(board)
    width = len(board[0])

    clickedX = readFromOffset(pm, CLICK_X_OFFSET) - 1
    clickedY = readFromOffset(pm, CLICK_Y_OFFSET) - 1

    print(f"User first clicked at: ({clickedX}, {clickedY})")

    mousePosition = mouse.position

    global BOARD_ORIGIN

    BOARD_ORIGIN = (
        mousePosition[0] - clickedX * CELL_SIZE,
        mousePosition[1] - clickedY * CELL_SIZE,
    )

    print(f"Board origin set at: {BOARD_ORIGIN}")

    currentPosition = (clickedX, clickedY)

    while True:
        # END_GAME_STATE is the sole source of truth for whether
        # the active game has ended.
        gameState = readFromOffset(
            pm,
            END_GAME_STATE
        )

        if gameState != 0:
            return gameState

        board = getBoardValues(pm)

        safeMoves = deduceSafeCells(board)

        if not safeMoves:
            guess = findRandomSafeGuess(board)

            if guess is None:
                currentPosition = fallbackExploreAll(
                    pm,
                    currentPosition
                )
                continue

            safeMoves = {guess}

        moved = False

        for target in safeMoves:
            path = bfsPath(
                currentPosition,
                target,
                width,
                height
            )

            if not path:
                continue

            for x, y in path[1:]:
                # Stop immediately if Minesweeper reports the game
                # has ended while traversing the path.
                gameState = readFromOffset(
                    pm,
                    END_GAME_STATE
                )

                if gameState != 0:
                    return gameState

                if clickIfUnopened(pm, x, y):
                    currentPosition = (x, y)
                    moved = True
                    time.sleep(POLL_INTERVAL)

            if moved:
                break

        if not moved:
            currentPosition = fallbackExploreAll(
                pm,
                currentPosition
            )


def gameLoop(pm: pymem.Pymem) -> None:
    """Wait for, solve and report Minesweeper games indefinitely."""
    while True:
        startTime = waitForGameStart(pm)

        gameState = solveGame(
            pm,
            startTime
        )

        elapsed = time.perf_counter() - startTime

        match gameState:
            case 2:
                print("[Loss] ", end="")
            case 3:
                print("[Win] ", end="")
            case 0:
                print("[Reset] ", end="")
            case _:
                print(f"[State {gameState}] ", end="")

        print(f"Time elapsed: {elapsed:.3f}")
        print("-" * 21)

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
