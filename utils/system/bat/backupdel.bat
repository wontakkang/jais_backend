@echo off
forfiles /s /p D:\backup\ /d -7 /m *.* /c "cmd /c del @path"