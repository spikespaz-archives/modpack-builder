import sys
import platform


PLATFORM = platform.platform()
IS_VIRTUAL_ENV = hasattr(sys, "real_prefix")  # Check to see if this is a virtual environment
