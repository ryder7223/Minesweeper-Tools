'''
Works on Windows XP Minesweeper version 5.1.2600
If you use another version, you will have to find
the offsets that version uses
'''
import subprocess
import importlib
import sys

required_modules = ['pynput', 'pymem']

def install_missing_modules(modules):
    try:
        import pip
    except ImportError:
        print("pip is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"{module} is not installed. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

install_missing_modules(required_modules)

import subprocess
import importlib
import sys
import time
import os
import random
from collections import deque
from pynput.mouse import Controller, Button
import pymem
import pymem.process

# Constants
PROCESS_NAME = "winmine.exe"
BASE_OFFSET = 0x5361
WIDTH_OFFSET = 0x5334
HEIGHT_OFFSET = 0x5338
CLICK_X_OFFSET = 0x5118
CLICK_Y_OFFSET = 0x511C
CELL_SIZE = 16
SAFE_VALUES = [15]
BOMB_VALUE = 143
NUMBER_VALUES = {i: i - 64 for i in range(65, 73 + 1)}  # 65–72 → 1–8
mouse = Controller()
BOARD_ORIGIN = (0, 0)
global right, left
right = Button.right
left = Button.left

def cclick(button, duration):
    mouse.press(button)
    time.sleep(duration)
    mouse.release(button)

def move_and_left_click(x, y):
    screen_x = BOARD_ORIGIN[0] + (x * CELL_SIZE)
    screen_y = BOARD_ORIGIN[1] + (y * CELL_SIZE)
    mouse.position = (screen_x, screen_y)
    cclick(left, 0)
    #time.sleep(0.05)

def move_and_right_click(x, y):
    screen_x = BOARD_ORIGIN[0] + (x * CELL_SIZE)
    screen_y = BOARD_ORIGIN[1] + (y * CELL_SIZE)
    mouse.position = (screen_x, screen_y)
    cclick(right, 0)
    #time.sleep(0.05)

def read_board(pm, base_address, start_offset, row_count, col_count):
    board = []
    for row in range(row_count):
        row_offset = start_offset + (row * 0x20)
        row_data = pm.read_bytes(base_address + row_offset, col_count)
        board.append(list(row_data))
    return board

def wait_for_first_click(pm, module_base, row_count, col_count):
    print("Waiting for user to click a square...")
    prev_board = read_board(pm, module_base, BASE_OFFSET, row_count, col_count)
    while True:
        time.sleep(0.01)
        new_board = read_board(pm, module_base, BASE_OFFSET, row_count, col_count)
        if new_board != prev_board:
            flat = [byte for row in new_board for byte in row]
            if any(val not in (15, 143) for val in flat):
                print("First click detected.")
                return new_board
            else:
                prev_board = new_board

def find_number_cells(board):
    number_cells = {}
    for y, row in enumerate(board):
        for x, cell in enumerate(row):
            if cell in NUMBER_VALUES:
                number_cells[(x, y)] = NUMBER_VALUES[cell]
    return number_cells

def deduce_safe_cells(board):
    number_cells = find_number_cells(board)
    safe_cells = set()
    for (x, y), number in number_cells.items():
        neighbors = get_neighbors(x, y, len(board[0]), len(board))
        hidden = [pos for pos in neighbors if board[pos[1]][pos[0]] in (15, 143)]
        bombs = [pos for pos in neighbors if board[pos[1]][pos[0]] == BOMB_VALUE]
        if len(bombs) == number:
            for pos in hidden:
                if board[pos[1]][pos[0]] == 15:
                    safe_cells.add(pos)
    return safe_cells

def get_neighbors(x, y, width, height):
    return [
        (nx, ny)
        for nx in range(x - 1, x + 2)
        for ny in range(y - 1, y + 2)
        if (0 <= nx < width and 0 <= ny < height and not (nx == x and ny == y))
    ]

def bfs_path(board, start, goal, width, height):
    queue = deque([[start]])
    seen = set([start])
    while queue:
        path = queue.popleft()
        x, y = path[-1]
        if (x, y) == goal:
            return path
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen:
                # Allow passing over all tiles
                seen.add((nx, ny))
                queue.append(path + [(nx, ny)])
    return []

def validate_and_click(pm, module_base, x, y, col_count):
    address = module_base + BASE_OFFSET + (y * 0x20) + x
    value = pm.read_uchar(address)
    if value == BOMB_VALUE:
        move_and_right_click(x, y)
        return False
    elif value == 15:
        move_and_left_click(x, y)
        return True
    return False

def fallback_explore_all(pm, module_base, board, start_pos, col_count, row_count):
    current_pos = start_pos
    while True:
        board = read_board(pm, module_base, BASE_OFFSET, row_count, col_count)
        unclicked = [(x, y) for y in range(row_count) for x in range(col_count) if board[y][x] == 15]
        if not unclicked:
            return current_pos
        best_target = None
        best_path = None
        for target in unclicked:
            path = bfs_path(board, current_pos, target, col_count, row_count)
            if path:
                if best_path is None or len(path) < len(best_path):
                    best_path = path
                    best_target = target
        if best_path:
            for step in best_path[1:]:
                x, y = step
                if validate_and_click(pm, module_base, x, y, col_count):
                    current_pos = (x, y)
                    time.sleep(0.01)
        else:
            return current_pos

def find_random_safe_guess(board):
    height = len(board)
    width = len(board[0]) if height > 0 else 0
    candidates = [(x, y) for y in range(height) for x in range(width) if board[y][x] == 15]
    return random.choice(candidates) if candidates else None

def game_loop(pm, module_base):
    global BOARD_ORIGIN
    prev_col_count = pm.read_int(module_base + WIDTH_OFFSET)
    prev_row_count = pm.read_int(module_base + HEIGHT_OFFSET)
    print(f"Board size: {prev_col_count}x{prev_row_count}")
    wait_for_first_click(pm, module_base, prev_row_count, prev_col_count)
    clicked_x = pm.read_int(module_base + CLICK_X_OFFSET) - 1
    clicked_y = pm.read_int(module_base + CLICK_Y_OFFSET) - 1
    print(f"User first clicked at: ({clicked_x}, {clicked_y})")
    mouse_pos = mouse.position
    BOARD_ORIGIN = (
        mouse_pos[0] - (clicked_x * CELL_SIZE),
        mouse_pos[1] - (clicked_y * CELL_SIZE),
    )
    print(f"Board origin set at: {BOARD_ORIGIN}")
    current_pos = (clicked_x, clicked_y)
    while True:
        col_count = pm.read_int(module_base + WIDTH_OFFSET)
        row_count = pm.read_int(module_base + HEIGHT_OFFSET)
        if col_count != prev_col_count or row_count != prev_row_count:
            print("Board size changed. Restarting loop.")
            return
        board = read_board(pm, module_base, BASE_OFFSET, row_count, col_count)
        flat = [cell for row in board for cell in row]
        if 15 not in flat:
            print("No unopened tiles left. Game completed.")
            return
        if set(flat) <= {15, BOMB_VALUE}:
            print("Board cleared or reset. Restarting loop.")
            return
        safe_moves = deduce_safe_cells(board)
        if not safe_moves:
            guess = find_random_safe_guess(board)
            if not guess:
                current_pos = fallback_explore_all(pm, module_base, board, current_pos, col_count, row_count)
                continue
            safe_moves = {guess}
        moved = False
        for target in safe_moves:
            path = bfs_path(board, current_pos, target, col_count, row_count)
            if not path:
                continue
            for step in path[1:]:
                x, y = step
                if validate_and_click(pm, module_base, x, y, col_count):
                    current_pos = (x, y)
                    moved = True
                    time.sleep(0.01)
            if moved:
                break
        if not moved:
            current_pos = fallback_explore_all(pm, module_base, board, current_pos, col_count, row_count)

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    try:
        pm = pymem.Pymem(PROCESS_NAME)
        module_base = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME).lpBaseOfDll
        while True:
            game_loop(pm, module_base)
    except pymem.exception.ProcessNotFound:
        print(f"Error: Process '{PROCESS_NAME}' not found.")
    except Exception as e:
        print(f"Unexpected error occurred:\n{e}")

if __name__ == "__main__":
    main()