@echo off

if exist "%localappdata%\Microsoft\Windows\Fonts\SourceCodePro-Regular.ttf" exit

copy "fonts/SourceCodePro-Regular.ttf" "%localappdata%\Microsoft\Windows\Fonts"

reg add ^
    "HKCU\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" ^
    /v "Source Code Pro (TrueType)" ^
    /t "REG_SZ" ^
    /d "%localappdata%\Microsoft\Windows\Fonts\SourceCodePro-Regular.ttf"
