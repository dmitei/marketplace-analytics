"""Create demo CSVs and SQLite database on first dashboard launch."""
from pathlib import Path
from threading import Lock
from .config import DB, DEMO, FILES
from .demo import generate_demo
from .etl import load_csvs

_lock = Lock()


def ensure_demo_database(db_path: Path = DB, demo_dir: Path = DEMO) -> Path:
    """Reuse an existing database; initialize missing data with the fixed demo seed."""
    db_path, demo_dir = Path(db_path), Path(demo_dir)
    with _lock:
        if db_path.is_file():
            return db_path
        if not all((demo_dir / filename).is_file() for filename in FILES.values()):
            generate_demo(demo_dir)
        load_csvs(demo_dir, db_path)
    return db_path
