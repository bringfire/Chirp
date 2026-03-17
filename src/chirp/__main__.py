"""Entry point: python -m chirp"""

import os
import socket

import uvicorn
from dotenv import load_dotenv

load_dotenv()

requested_port = int(os.environ.get("CHIRP_PORT", "0"))
reload = os.environ.get("CHIRP_RELOAD", "0") == "1"

# Pre-bind to discover the actual port (supports OS-assigned port 0).
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("127.0.0.1", requested_port))
actual_port = sock.getsockname()[1]

# Communicate actual port to server.py (imported by uvicorn later)
os.environ["_CHIRP_BOUND_PORT"] = str(actual_port)

if reload:
    # Reload mode can't pass sockets across subprocess boundaries;
    # close and let uvicorn rebind to the known port.
    sock.close()
    uvicorn.run("chirp.server:app", host="127.0.0.1", port=actual_port, reload=True)
else:
    # Pass the pre-bound socket directly — no close/rebind race.
    config = uvicorn.Config("chirp.server:app", host="127.0.0.1")
    server = uvicorn.Server(config)
    server.run(sockets=[sock])
