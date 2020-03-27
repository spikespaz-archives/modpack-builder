@echo off

title Minecraft Modpack Installer by Jacob Birkett

call "modpack_builder.dist\modpack_builder.exe" -m update -z "modpack.zip" --concurrent-requests 1 --concurrent-downloads 1

set /p=Press ENTER to exit.
