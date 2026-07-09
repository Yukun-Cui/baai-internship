# FlagGems PR Submit Data

This directory keeps the mutable data files used by the skill:

- `规范名.xlsx`: canonical operator names and PR link backfill target.
- `第一批pr算子.xlsx`: pending operator list and expected speedup data.
- `pr状态记录.md`: submission failures, warnings, and PR events.

The scripts use this directory by default. Override with `FLAGGEMS_PR_SUBMIT_DATA_DIR`
or the file-specific variables `FLAGGEMS_NORM_XLSX`, `FLAGGEMS_PR_XLSX`, and
`FLAGGEMS_PR_RECORD_PATH`.
