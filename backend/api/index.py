import sys
from pathlib import Path

# Add project root to sys.path for Vercel Serverless Function execution
ROOT_DIR = Path(__file__).parent.parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.api.main import app
