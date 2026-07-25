# FlagGems PR Submit (MThreads) Data

本目录存放摩尔线程 skill 使用的可变数据文件：

- `pr状态记录.md`: 提交流程中的失败、warning、低加速比、PR 事件记录（本 skill 独有）。

## 共享数据（默认复用通用版）

规范命名映射和待提交列表默认复用 `flaggems-pr-submit/data/`，不在本目录重复维护：

- `规范名.xlsx`: 规范命名映射 + PR 链接回填目标。
- `第一批pr算子.xlsx`: 待提交算子列表 + 预期加速比。

`operator_registry.py` 的解析顺序：**环境变量覆盖 → 本地 `data/` → 通用版 `../flaggems-pr-submit/data/`**。
即：把上述 xlsx 放到本目录会优先使用本地副本，否则回退到通用版共享副本。

## 环境变量覆盖

- `FLAGGEMS_NORM_XLSX`: 规范名表路径
- `FLAGGEMS_PR_XLSX`: 待提交列表路径
- `FLAGGEMS_PR_RECORD_PATH`: PR 状态记录路径（默认本目录 `pr状态记录.md`）
