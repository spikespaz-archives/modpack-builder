import sys
import platform

from distribution_tools.pyinstaller_wrapper import pyinstaller_compile


PLATFORM = platform.platform()
IS_VIRTUAL_ENV = hasattr(sys, "real_prefix")  # Check to see if this is a virtual environment
