import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_quiet_hours_ends_at_survives_dst():
    script = Path(__file__).parent / "js" / "quiet_hours.mjs"
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
