"""Entry point: python -m chirp"""

import atexit
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

load_dotenv()

port = int(os.environ.get("CHIRP_PORT", "9900"))

# Write discovery file so Rook can find us
DISCOVERY_FOLDER = Path(tempfile.gettempdir()) / "rook"
DISCOVERY_FILE = DISCOVERY_FOLDER / f"chirp-service-{port}.json"


def _write_discovery():
    DISCOVERY_FOLDER.mkdir(parents=True, exist_ok=True)
    payload = {
        "service": "chirp",
        "port": port,
        "pid": os.getpid(),
        "home": str(Path(__file__).resolve().parent.parent.parent),
        "startTime": datetime.now().isoformat(timespec="seconds"),
    }
    DISCOVERY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _cleanup_discovery():
    try:
        DISCOVERY_FILE.unlink(missing_ok=True)
    except OSError:
        pass


_write_discovery()
atexit.register(_cleanup_discovery)

uvicorn.run("chirp.server:app", host="0.0.0.0", port=port, reload=True)
