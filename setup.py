#!/usr/bin/env python3
# https://godatadriven.com/blog/a-practical-guide-to-using-setup-py/
__descr__ = "A set of toolkit for faculty members in the Xidian University."

import sys

# Compatibility with Python3
if sys.version_info[0] < 3:
    import __builtin__ as builtins
else:
    import builtins

# Global variable for detecting if we are during setup
builtins.__XDUFACOOL_SETUP__ = True

DISTNAME = "xdufacool"
with open("README.md") as readme:
    LONG_DESCRIPTION = readme.read()
MAINTAINER = "Fei Qi"
MAINTAINER_EMAIL = "fred.qi@ieee.org"
URL= "https://github.com/fredqi/xdufacool"
with open("LICENSE") as f:
    LICENSE = f.read()

# Import a restricted version
import xdufacool
VERSION = xdufacool.__version__

try:
    from setuptools import setup
    from setuptools import find_packages
except ImportError:
    from distutils.core import setup

def setup_package():
    """Setup the package."""
    metadata = dict(name=DISTNAME,
                    version=VERSION,
                    maintainer=MAINTAINER,
                    description=__descr__,
                    license=LICENSE,
                    url=URL,
                    packages=find_packages(include=('xdufacool',)),
                    install_requires=['PySocks'],
                    # scripts
                    entry_points={'console_scripts':
                                      ['xdufacool = xdufacool.homework_manager:check_homeworks',
                                       'pdf2pptx  = xdufacool.pdf2pptx:pdf2pptx',
                                       'syllabus  = xdufacool.syllabus:syllabus_helper',
                                       'xduscore  = xdufacool.score_helper:xduscore',
                                       'arxort = xdufacool.organize_bib:organize_bib',
                                       'invoice_helper = xdufacool.invoice:collect_invoice']},
                    # unit tests
                    test_suite="tests",
                    package_data={
                        'xdufacool': ['templates/*.tex.j2'],
                    },
                    include_package_data=True)
    if (len(sys.argv) >= 2
        and ('--help' in sys.argv[1:] or sys.argv[1]
             in ('--help-commands', 'egg_info', '--version'))):
        metadata['version'] = VERSION

    setup(**metadata)


if __name__ == '__main__':
    setup_package()
