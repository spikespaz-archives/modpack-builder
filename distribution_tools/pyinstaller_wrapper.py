import logging
import platform

from enum import Enum
from pathlib import Path

import PyInstaller.log
import PyInstaller.compat
import PyInstaller.__main__

from distribution_tools import PLATFORM


class LogLevel(Enum):
    trace = "TRACE"
    debug = "DEBUG"
    info = "INFO"
    warn = "WARN"
    error = "ERROR"
    critical = "CRITICAL"


class DebugMode(Enum):
    all = "all"
    imports = "imports"
    bootloader = "bootloader"
    noarchive = "noarchive"


pyinstaller_default_arguments = {
    "onefile": False,
    "specpath": None, 
    "name": None, 
    "datas": list(),
    "binaries": list(),
    "pathex": list(),
    "hiddenimports": list(),
    "hookspath": list(),
    "runtime_hooks": list(),
    "excludes": list(),
    "key": None,
    "debug": list(),
    "strip": False, 
    "noupx": False, 
    "upx_exclude": None, 
    "console": True,
    "icon_file": None, 
    "version_file": None, 
    "manifest": None, 
    "resources": list(),
    "uac_admin": False,
    "uac_uiaccess": False,
    "win_private_assemblies": False,
    "win_no_prefer_redirects": False,
    "bundle_identifier": None, 
    "runtime_tmpdir": None, 
    "bootloader_ignore_signals": False,
    "distpath": None,  # "distpath": "C:\\Users\\spike\\Documents\\github.com\\spikespaz\\modpack-builder\\dist",
    "workpath": None,  # "workpath": "C:\\Users\\spike\\Documents\\github.com\\spikespaz\\modpack-builder\\build",
    "noconfirm": False,
    "upx_dir": None, 
    "ascii": False, 
    "clean_build": False, 
    "loglevel": "INFO",
    "filenames": None  # "filenames": ["pyinstaller_wrapper.py"]
}


def __convert_types(object_):
    if isinstance(object_, dict):
        replacement = dict()

        for key, value in object_.items():
            replacement[key] = __convert_types(value)

        return replacement

    elif isinstance(object_, tuple):
        replacement = list()

        for value in object_:
            replacement.append(__convert_types(value))

        return replacement

    elif isinstance(object_, Path):
        # There is a bug with PyInstaller 3.6 on Windows in 'PyInstaller\building\build_main.py' on line 636,
        # to work around this we must replace backslashes in paths with forward-slashes.
        # In PyInstaller, the line that calls `os.makedirs` raises an exception like this:
        #     OSError: [WinError 123] The filename, directory name,
        #     or volume label syntax is incorrect: "<bound method Path.resolve of WindowsPath('C:"
        # This indicates that somewhere along the call-chain a function is mangling the handling of the WindowsPath
        # object. Possibly attempting to convert the path to a string without using 'str' as it should.
        return "/".join(object_.resolve().parts)

    elif isinstance(object_, Enum):
        return object_.value

    else:
        return object_


def pyinstaller_compile(filenames, pyi_config=None, **kwargs):
    for name in kwargs:
        if name not in pyinstaller_default_arguments:
            raise KeyError(f"PyInstaller has no argument: {name}")
        
    PyInstaller.compat.check_requirements()

    kwargs["filenames"] = filenames

    if "distpath" not in kwargs:
        kwargs["distpath"] = Path.cwd() / "dist"

    if "workpath" not in kwargs:
        kwargs["workpath"] = Path.cwd() / "build"

    kwargs = __convert_types(kwargs)

    arguments = pyinstaller_default_arguments.copy()
    arguments.update(kwargs)

    logger = PyInstaller.log.getLogger(__name__)
    
    try:
        loglevel = getattr(logging, arguments["loglevel"].upper())
    except AttributeError:
        logger.error(f"Unknown log level '{arguments['loglevel']}'")
    else:
        logger.setLevel(loglevel)

    logger.info(f"PyInstaller: {PyInstaller.__version__}")
    logger.info(f"Python: {platform.python_version()}{' (conda)' if PyInstaller.compat.is_conda else str()}")
    logger.info(f"Platform: {PLATFORM}")

    try:
        if not (spec_file := arguments["filenames"][0]).endswith(".spec"):
            spec_file = PyInstaller.__main__.run_makespec(**arguments)

        PyInstaller.__main__.run_build(pyi_config, spec_file, **arguments)

    except KeyboardInterrupt:
        raise SystemExit("Aborted by user request.")
