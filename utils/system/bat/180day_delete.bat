@echo off
forfiles /p D:\logs\ /s /m *.* /d -180 /c "cmd /c del @file"
