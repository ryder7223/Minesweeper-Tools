import subprocess
import importlib
import sys

required_modules = ['pymem']

def install_missing_modules(modules):
    try:
        pip = 'pip'
        importlib.import_module(pip)
    except ImportError:
        print(f"{pip} is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"{module} is not installed. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

install_missing_modules(required_modules)

import pymem
import pymem.process
import os
 '''
Commented out code is from past versions of the script.
 '''
def read_board(pm, base_address, start_offset, row_count=30, col_count=30, row_stride=0x20):
    board = []
    for row in range(row_count):
        row_offset = start_offset + (row * row_stride)
        row_bytes = pm.read_bytes(base_address + row_offset, col_count)
        #row_symbols = ['X' if byte == 143 else 'O' for byte in row_bytes]
        row_symbols = ['\033[91mX\033[0m' if byte == 143 else 'O' for byte in row_bytes]
        #board.append([byte for byte in row_bytes])
        board.append(row_symbols)
    return board

def main():
    os.system('cls')
    process_name = "winmine.exe"
    base_offset = 0x5361  # Offset of the first cell (top-left)
    width_offset = 0x5334
    height_offset = 0x5338

    try:
        pm = pymem.Pymem(process_name)
        module_base = pymem.process.module_from_name(pm.process_handle, process_name).lpBaseOfDll

        # Read width and height dynamically from process memory
        col_count = pm.read_int(module_base + width_offset)
        row_count = pm.read_int(module_base + height_offset)

        board = read_board(pm, module_base, base_offset, row_count=row_count, col_count=col_count)

        os.system('cls')
        for row in board:
            #print(row)
            print(' '.join(row))

    except pymem.exception.ProcessNotFound:
        print(f"Error: Process '{process_name}' not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    input("Press Enter to exit...")
    os.system('cls')

if __name__ == "__main__":
    main()