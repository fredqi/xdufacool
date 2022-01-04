__version__ = "0.6.0"

import sys

try:
    # This variable is injected in the __builtins__ by the build
    # process. It used to enable importing subpackages of sklearn when
    # the binaries are not built
    __XDUFACOOL_SETUP__
except NameError:
    __XDUFACOOL_SETUP__ = False

if __XDUFACOOL_SETUP__:
    sys.stderr.write("Partial import of xdufacool during the build process.\n")
    # We are not importing the rest of the package during the build
else:
    __all__ = ["check_homeworks"]
    from .homework_manager import check_homeworks
