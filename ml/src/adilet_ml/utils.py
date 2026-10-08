"""Small shared utilities for reproducible ML scripts."""

from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np


def repo_root(start: Path | None = None) -> Path:
    """Return the repository root by walking up to a directory containing `contracts/`."""
    current = (start or Path.cwd()).resolve()
    for path in (current, *current.parents):
        if (path / "contracts").is_dir() and (path / "docs").is_dir():
            return path
    return current


def seed_everything(seed: int = 42) -> None:
    """Seed Python, NumPy, and torch when torch is installed."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch
    except ImportError:
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
