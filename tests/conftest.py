"""Point the checkpointer DB at a temp file during tests.

Set before any test imports `agent.graph` (whose module-level `graph` builds a
SqliteSaver at import time), so tests never touch the repo's data/ dir.
"""

import os
import tempfile

os.environ.setdefault(
    "CHECKPOINT_DB", os.path.join(tempfile.gettempdir(), "trip_agent_test_cp.sqlite")
)
