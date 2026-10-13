#Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Run external commands with captured output; shared by transfers and ROOT merging."""

import subprocess
from typing import Optional, Sequence


def run_command(arguments: Sequence[str], timeout: Optional[float]) -> subprocess.CompletedProcess:
    """Capture output and preserve command, exit status and diagnostics on failure."""
    result = subprocess.run(list(arguments), shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
    return result
