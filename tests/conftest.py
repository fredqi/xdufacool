import os
import sys
import warnings
import pytest

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 

def pytest_configure(config):
    """Configure pytest to handle deprecation warnings."""
    os.environ['JUPYTER_PLATFORM_DIRS'] = '1'
    warnings.simplefilter('ignore', DeprecationWarning)
    # warnings.filterwarnings(
    #     "ignore",
    #     message="Jupyter is migrating its paths to use standard platformdirs",
    #     category=DeprecationWarning,
    # ) 