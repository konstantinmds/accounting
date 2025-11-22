import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:devpassword@localhost:5432/postgres")
