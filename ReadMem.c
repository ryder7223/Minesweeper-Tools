#include <windows.h>
#include <tlhelp32.h>
#include <psapi.h>
#include <stdio.h>

#define PROCESS_NAME "winmine.exe"
// Build: cl winmine_reader.c /link psapi.lib
// Offsets for classic Minesweeper
#define BASE_OFFSET  0x5361
#define WIDTH_OFFSET 0x5334
#define HEIGHT_OFFSET 0x5338
#define ROW_STRIDE   0x20

DWORD FindProcessId(const char* processName) {
    PROCESSENTRY32 processEntry;
    processEntry.dwSize = sizeof(PROCESSENTRY32);

    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE)
        return 0;

    if (Process32First(snapshot, &processEntry)) {
        do {
            if (_stricmp(processEntry.szExeFile, processName) == 0) {
                DWORD pid = processEntry.th32ProcessID;
                CloseHandle(snapshot);
                return pid;
            }
        } while (Process32Next(snapshot, &processEntry));
    }

    CloseHandle(snapshot);
    return 0;
}

void SetConsoleColor(WORD color) {
    HANDLE hConsole = GetStdHandle(STD_OUTPUT_HANDLE);
    SetConsoleTextAttribute(hConsole, color);
}

void ReadBoard(HANDLE hProcess, uintptr_t baseAddress, int startOffset, int rowCount, int colCount) {
    BYTE buffer[32];
    for (int row = 0; row < rowCount; row++) {
        int rowOffset = startOffset + (row * ROW_STRIDE);
        SIZE_T bytesRead;
        if (ReadProcessMemory(hProcess, (LPCVOID)(baseAddress + rowOffset), buffer, colCount, &bytesRead)) {
            for (int col = 0; col < colCount; col++) {
                if (buffer[col] == 0x8F) {
                    SetConsoleColor(FOREGROUND_RED | FOREGROUND_INTENSITY);
                    printf("X ");
                    SetConsoleColor(FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE); // reset to white
                } else {
                    printf("O ");
                }
            }
            printf("\n");
        } else {
            printf("Failed to read row %d\n", row);
        }
    }
}

int main() {
    DWORD pid = FindProcessId(PROCESS_NAME);
    if (pid == 0) {
        printf("Error: Process '%s' not found.\n", PROCESS_NAME);
        return 1;
    }

    HANDLE hProcess = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, FALSE, pid);
    if (!hProcess) {
        printf("Error: Failed to open process.\n");
        return 1;
    }

    HMODULE hMods[1024];
    DWORD cbNeeded;
    if (!EnumProcessModules(hProcess, hMods, sizeof(hMods), &cbNeeded)) {
        printf("Error: Could not enumerate process modules.\n");
        CloseHandle(hProcess);
        return 1;
    }

    uintptr_t baseAddress = (uintptr_t)hMods[0];
    int width = 0, height = 0;
    SIZE_T bytesRead;

    ReadProcessMemory(hProcess, (LPCVOID)(baseAddress + WIDTH_OFFSET), &width, sizeof(int), &bytesRead);
    ReadProcessMemory(hProcess, (LPCVOID)(baseAddress + HEIGHT_OFFSET), &height, sizeof(int), &bytesRead);

    ReadBoard(hProcess, baseAddress, BASE_OFFSET, height, width);

    CloseHandle(hProcess);

    printf("Press Enter to exit...");
    getchar();
    return 0;
}