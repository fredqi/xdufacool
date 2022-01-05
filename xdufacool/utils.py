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

# https://stackoverflow.com/questions/14058453/
# making-python-loggers-output-all-messages-to-stdout-in-addition-to-log-file
def setup_logging(logfile, level):
    """Set up logging to both a file and stdout."""

    handlers = [logging.FileHandler(logfile),
                logging.StreamHandler(sys.stdout)]
    handlers[1].setLevel(logging.INFO)
    log_format = '%(asctime)s, %(levelname)8s, %(message)s'
    logging.basicConfig(level=level,
                        format=log_format,
                        datefmt='%Y-%m-%d %H:%M:%S',
                        handlers=handlers)

# 
# utils.py ends here
