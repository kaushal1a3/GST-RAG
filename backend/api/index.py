import sys
import os
from pathlib import Path

# Use /tmp for model caches in serverless environment
os.environ["HF_HOME"] = "/tmp"
os.environ["FASTEMBED_CACHE_PATH"] = "/tmp"

# Add project root to sys.path for Vercel Serverless Function execution
ROOT_DIR = Path(__file__).parent.parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.main import app

