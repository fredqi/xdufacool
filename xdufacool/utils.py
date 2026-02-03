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
import os
import sys
import shutil
import subprocess
import tempfile
import yaml
import logging
import logging.config
from pathlib import Path
from typing import Union, List

def setup_logging(log_level=logging.INFO):
    config_path = Path(__file__).parent / "logging.yaml"
    with config_path.open() as f:
        config = yaml.safe_load(f)
        level_name = logging.getLevelName(log_level)
        file_handler_conf = config.get("handlers", {}).get("file_handler", {})
        if level_name and file_handler_conf:
            config['root']['level'] = level_name
            file_handler_conf["level"] = level_name

        logging.config.dictConfig(config)

# https://stackoverflow.com/questions/14058453/
# making-python-loggers-output-all-messages-to-stdout-in-addition-to-log-file
def setup_logging_previous(logfile, level=logging.INFO, stdout_level=logging.WARNING):
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

def format_list(items, conj="and", lang="en"):
    """
    Formats a list of items into a string separated by commas or enumeration marks,
    with a specified conjunction before the last item, supporting both English and Chinese.

    Args:
        items (list): A list of items (can be any type that has a string representation).
        conj (str): The conjunction to use before the last item. 
                    Default is "and" for English and "和" for Chinese.
        lang (str): Language code - "en" for English, "zh" for Chinese.

    Returns:
        str: A formatted string of items.
    """
    if not items:
        return ""
    if len(items) == 1:
        return str(items[0])
    elif len(items) == 2:
        conj = "、" if lang == "zh" else " and "
        return f"{items[0]}{conj}{items[1]}"
    else:
        # Chinese format: item1、item2、item3和item4
        # English format: item1, item2, item3, and item4
        sep = "、" if lang == "zh" else ", "
        ret = sep.join([str(item) for item in items[:-1]])
        if lang == "zh":
            if conj == "and":
                conj = "和"
            ret += f"{conj}{items[-1]}"
        else:
            ret += f"{sep} {conj} {items[-1]}"
        return ret

def load_config(filepath, keyword):
    """
    Loads a YAML config file, extracts data for a specific keyword,
    and performs variable substitution.

    Args:
        filepath: Path to the YAML config file.
        keyword: The keyword to extract data for (e.g., "teachers", "students").

    Returns:
        A dictionary containing the data for the specified keyword,
        with variables substituted, or None if the keyword is not found.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.error(f"Error: Config file not found at {filepath}")
        return None
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file: {e}")
        return None

    if keyword not in config:
        logging.error(f"Error: Keyword '{keyword}' not found in config file.")
        return None

    return config[keyword]

def is_tool_installed(name):
    return shutil.which(name) is not None

def repack_archive(file_path, remove_original=False, dry_run=False):
    """Repack .rar and .7z archives to .zip format."""
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    base_name, ext = os.path.splitext(filename)
    
    # Target zip file path
    zip_path = os.path.join(directory, base_name + ".zip")
    
    if os.path.exists(zip_path):
        logging.info(f"[SKIP] Target zip already exists: {zip_path}")
        return False

    if dry_run:
        logging.info(f"[DRY RUN] Would repack: {file_path} -> {zip_path}")
        if remove_original:
            logging.info(f"          And delete original: {file_path}")
        return True

    logging.info(f"[PROCESSING] {file_path}...")

    # Create a temporary directory for extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        # extraction command using 7z
        # -y: assume yes on all queries (overwrite)
        # -o{dir}: set output directory (no space between -o and dir)
        cmd = ["7z", "x", file_path, f"-o{temp_dir}", "-y"]
        
        try:
            # Suppress output unless error
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"[ERROR] Failed to extract {filename}:")
                logging.error(result.stderr)
                return False
            
            # Repack to zip
            # shutil.make_archive creates a zip file. 
            # root_dir is the directory to start archiving from (temp_dir)
            # base_name is the path to the zip file (excluding .zip extension)
            shutil.make_archive(os.path.join(directory, base_name), 'zip', temp_dir)
            logging.info(f"[SUCCESS] Created {zip_path}")
            
            if remove_original:
                os.remove(file_path)
                logging.info(f"[REMOVED] Original file deleted: {file_path}")
                
            return True

        except Exception as e:
            logging.error(f"[ERROR] Exception processing {filename}: {e}")
            return False

def normalize_filename(filename):
    """Formalize filenames by removing carriage returns and newlines."""
    # Remove newlines and carriage returns
    new_name = filename.replace('\r', '').replace('\n', '')
    return new_name

# 
# utils.py ends here