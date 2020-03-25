@echo off

title Minecraft Modpack Installer by Jacob Birkett

call "font\install_font.bat"
call "modpack_builder.dist\modpack_builder.exe" update "modpack.zip"

set /p=Press ENTER to exit.
