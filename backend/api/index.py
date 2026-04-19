import sys
import os

os.environ["VERCEL"] = "1"
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/app.db")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402
from mangum import Mangum  # noqa: E402

handler = Mangum(app, lifespan="off")
