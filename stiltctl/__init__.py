import shutil
import subprocess
from pathlib import Path
from typing import Optional

from stiltctl.config import config_from_env


def install_stilt_if_missing(stilt_path: Optional[Path] = None):
    """Install STILT framework on local filesystem.

    For STILT installation documentation, see
        https://uataq.github.io/stilt/#/install

    In production, STILT is included in the stiltctl-backend docker image.
    """
    stilt_path = stilt_path or config_from_env.STILT_PATH
    hycs_std_path = stilt_path / "exe" / "hycs_std"
    if hycs_std_path.exists():
        return

    shutil.rmtree(stilt_path, ignore_errors=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/uataq/stilt", stilt_path],
        check=True,
    )
    subprocess.run(["./setup"], cwd=stilt_path, check=True)


install_stilt_if_missing()
