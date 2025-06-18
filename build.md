## How to build

1. **Set Up Visual Studio Installer**
     - Download Microsoft Visual Studio Build Tools from [here](https://visualstudio.microsoft.com/visual-cpp-build-tools) via the `Download Build Tools` button.
     - Complete the installation and run Visual Studio Installer, which will now be installed on your computer.
     - On Visual Studio Build Tools, click `Modify`.
     - Check `Desktop Development With C++`.
     - Click `Modify` on the bottom right.
2. **Build using x64 Native Tools**
     - Press the **Windows** key and search for `x64 Native Tools Command Prompt` and run the program.
     - Type `cd <Directory of the .c file>` into the new command prompt window.
     - Type `cl ReadMem.c /link psapi.lib` and it should build.
