import sys
from pathlib import Path

# Add backend directory to PYTHONPATH
BACKEND_ROOT = Path(__file__).parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Import the FastAPI app defined in backend/api/main.py
from backend.api.main import app
