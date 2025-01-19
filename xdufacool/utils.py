# utils.py ---
#
# Filename: utils.py
# Author: Fred Qi
# Created: 2022-01-05 08:53:59(+0800)
#
# Last-Updated: 2022-01-05 09:22:10(+0800) [by Fred Qi]
#     Update #: 33
# 

# Commentary:
#
#
# 

# Change Log:
#
#
#
import sys
import logging
from pathlib import Path
from typing import Union, List

# https://stackoverflow.com/questions/14058453/
# making-python-loggers-output-all-messages-to-stdout-in-addition-to-log-file
def setup_logging(logfile, level=logging.INFO, stdout_level=logging.WARNING):
    """
    Set up logging to both a file and stdout, with configurable levels for each.
    """
    handlers = [
        logging.FileHandler(logfile),
        logging.StreamHandler(sys.stdout)
    ]
    handlers[0].setLevel(level)
    handlers[1].setLevel(stdout_level)

    log_format = '%(asctime)s, %(levelname)8s, %(message)s'
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )

def validate_paths(base_path: Path, file_paths: Union[str, List[str]], description: str) -> List[Path]:
    """
    Validates file paths, handling both single paths and lists of paths.

    Args:
        base_path: The base path relative to which file paths are defined.
        file_paths: A single file path (str) or a list of file paths (List[str]).
        description: A description of the file type (for error messages).

    Returns:
        A list of valid Path objects.

    Raises:
        FileNotFoundError: If a file does not exist.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    valid_paths = []
    for item in file_paths:
        if not item:
            continue  # Skip empty strings or None
        file_path = base_path / item
        if file_path.exists():
            valid_paths.append(item)
        else:
            raise FileNotFoundError(f"{description} not found: {file_path}")

    return valid_paths

# 
# utils.py ends here
