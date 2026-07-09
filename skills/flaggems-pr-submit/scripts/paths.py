#!/usr/bin/env python3
"""Shared paths for the FlagGems PR submit skill."""

from __future__ import annotations

import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(
    os.environ.get("FLAGGEMS_PR_SUBMIT_DATA_DIR", SKILL_DIR / "data")
).expanduser()


def _resolve_data_file(env_name: str, filename: str) -> str:
    explicit = os.environ.get(env_name)
    if explicit:
        return str(Path(explicit).expanduser())
    return str(DATA_DIR / filename)


NORM_XLSX = _resolve_data_file("FLAGGEMS_NORM_XLSX", "规范名.xlsx")
PR_XLSX = _resolve_data_file("FLAGGEMS_PR_XLSX", "第一批pr算子.xlsx")
RECORD_PATH = _resolve_data_file("FLAGGEMS_PR_RECORD_PATH", "pr状态记录.md")
