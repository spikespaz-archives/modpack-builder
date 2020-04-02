@echo off

python -m nuitka --standalone --python-flag=-S --show-progress --show-scons --remove-output modpack_builder
