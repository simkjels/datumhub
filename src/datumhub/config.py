"""Runtime configuration — override via environment variables."""

from __future__ import annotations

import os
from pathlib import Path

# Path to the SQLite database file.
# Override with DATUMHUB_DB=/path/to/datumhub.db
DB_PATH = Path(os.environ.get("DATUMHUB_DB", "datumhub.db"))
