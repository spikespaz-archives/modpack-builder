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
    "distpath": None,
    # "distpath": "C:\\Users\\spike\\Documents\\github.com\\spikespaz\\modpack-builder\\dist",
    "workpath": None,
    # "workpath": "C:\\Users\\spike\\Documents\\github.com\\spikespaz\\modpack-builder\\build",
    "noconfirm": False,
    "upx_dir": None, 
    "ascii": False, 
    "clean_build": False, 
    "loglevel": "INFO",
    "filenames": None
    # "filenames": ["pyinstaller_wrapper.py"]
}


def pyinstaller_compile(filenames, pyi_config=None, **kwargs):
    for name in kwargs:
        if name not in pyinstaller_default_arguments:
            raise KeyError(f"PyInstaller has no argument: {name}")
        
    PyInstaller.compat.check_requirements()

    arguments = pyinstaller_default_arguments.copy()

    if (specpath := kwargs.get("specpath")) and isinstance(specpath, Path):
        kwargs["specpath"] = str(specpath.resolve())

    if datas := kwargs.get("datas"):
        kwargs["datas"] = list((str(path.resolve()) if isinstance(path, Path) else path) for path in datas)

    if pathex := kwargs.get("pathex"):
        kwargs["pathex"] = list((str(path.resolve()) if isinstance(path, Path) else path) for path in pathex)

    if hookspath := kwargs.get("hookspath"):
        kwargs["hookspath"] = list((str(path.resolve()) if isinstance(path, Path) else path) for path in hookspath)

    if runtime_hooks := kwargs.get("runtime_hooks"):
        kwargs["runtime_hooks"] = list(
            (str(path.resolve()) if isinstance(path, Path) else path) for path in runtime_hooks)

    if debug := kwargs.get("debug"):
        kwargs["debug"] = list((mode.value if isinstance(mode, DebugMode) else mode) for mode in debug)
        
    if (runtime_tmpdir := kwargs.get("runtime_tmpdir")) and isinstance(runtime_tmpdir, Path):
        kwargs["runtime_tmpdir"] = str(runtime_tmpdir.resolve())

    if distpath := kwargs.get("distpath"):
        if isinstance(distpath, Path):
            kwargs["distpath"] = str(distpath.resolve())

    if workpath := kwargs.get("distpath"):
        if isinstance(workpath, Path):
            kwargs["distpath"] = str(workpath.resolve())
            
    if (upx_dir := kwargs.get("upx_dir")) and isinstance(upx_dir, Path):
        kwargs["upx_dir"] = str(upx_dir.resolve())
        
    if (loglevel := kwargs.get("loglevel")) and isinstance(loglevel, LogLevel):
        kwargs["loglevel"] = loglevel.value
        
    kwargs["filenames"] = list((str(path.resolve()) if isinstance(path, Path) else path) for path in filenames)

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
