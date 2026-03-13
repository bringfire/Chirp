"""Entry point: python -m chirp"""

import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

port = int(os.environ.get("CHIRP_PORT", "9900"))
uvicorn.run("chirp.server:app", host="0.0.0.0", port=port, reload=True)
