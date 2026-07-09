# flaggems-pass-opt

用编译器优化 Pass 驱动 FlagGems 算子优化的 skill。把 FlagTree 编译器的优化 Pass（LICM、强度削减、Canonicalizer、CSE 等）当成一份人工优化清单，在 FlagGems 算子源码层逐条核对、手工落地。核心论据：编译器 Pass 是保守的，而源码层拥有完整语义，能把这些优化做得更彻底，并按编译器优化的 pattern 组织代码、保证不漏掉机会。

它把「选 Pass + 选算子配对 → 在 FlagGems-opt 落地等价变换 → 正确性门禁 → orig/opt 双轨 A/B benchmark → 成功样例归档」串成一条固定流程。每个样例最终交付：用了哪个 Pass + 源码 diff + 正确性 100% 通过 + 标注了 GPU/harness 的 A/B 性能数据。

## 目录结构

| 路径 | 说明 |
|------|------|
| `SKILL.md` | agent 使用的主说明，含触发条件、`pass.sh` 用法、阶段 0–4 工作流和铁律 |
| `scripts/pass.sh` | 统一入口脚本，含 `gpu` / `reinstall` / `restart` / `test` / `all` 五个子命令 |

## 前置约定

skill 假设工作区按如下布局（脚本内 `BASE_DIR` 硬编码为 `/root/pass`）：

| 路径 | 作用 |
|------|------|
| `/root/pass/FlagGems/` | 基线（baseline），不要改，可 `git pull` 更新 |
| `/root/pass/FlagGems-opt/` | 改动版，所有优化 diff 落在这里 |
| `/root/pass/FlagTree/` | FlagTree 编译器源码，Pass 原理出处，需要时用它重编译 flagtree |
| `/root/pass/diff/<op>.diff` | 每个算子的优化 patch，`pass.sh test` 会 `git apply` 到 FlagGems-opt |
| `/root/pass/logs/<op>/` | A/B 产物：`orig.benchmark` / `opt.benchmark`、`orig.dump` / `opt.dump`、`changes.diff` |
| `/root/pass/results/<op>/` | 成功样例的归档文档 |

## 统一入口 `pass.sh`

所有环境操作走 `scripts/pass.sh` 的子命令：

| 子命令 | 作用 |
|------|------|
| `pass.sh gpu` | 扫描并锁定最闲置 GPU（按利用率、显存升序），回显 index |
| `pass.sh reinstall` | `FlagTree` git pull 后重装 flagtree（改了编译器本身后用） |
| `pass.sh restart` | `FlagGems` git pull 后 `rm -rf` 旧的、`cp -r` 出干净的 `FlagGems-opt` |
| `pass.sh test -g <op> [-c <dev\|auto>]` | A/B harness：orig/opt 各 uninstall → install -e → 带 `MLIR_ENABLE_DUMP=1` 跑 pytest benchmark |
| `pass.sh all -g <op> [-c <dev\|auto>]` | `restart` + `test` 一条龙 |

`-g/--gem` 指定算子（对应 `benchmark/test_<op>.py`），默认 `var`。`-c/--cuda` 指定 GPU index，省略或传 `auto` 时自动挑最闲置卡。

## 核心工作流

1. 准备环境：`pass.sh restart` 从基线复制干净的 FlagGems-opt；确认 A/B 跑在空闲卡上（`pass.sh gpu` 或 `-c auto`）。
2. 选 Pass：从 `pass源码级总结.md` 挑优化逻辑能在源码层手工复现的 Pass。
3. 选算子：按 Pass 的 pattern 用搜索工具匹配（如 LICM 找带 `range` 循环、循环体重复算 mask/指针的 kernel）；确认 benchmark 没被 `skipif` 跳过、不是 memory-bound 纯逐点算子。
4. 落地优化：只改 FlagGems-opt，严格按 Pass 语义做等价变换（不改数值结果），一次只落一个 Pass / 一个算子，diff 里注明用了哪个 Pass、为什么编译器不做、源码层为什么能做。
5. 正确性门禁：`pytest tests/test_<op>.py` 必须 100% 通过，不过就回上一步修。
6. A/B benchmark：`pass.sh test -g <op> -c <idle_gpu>`，对比 `logs/<op>/orig.benchmark` 与 `opt.benchmark` 里同一 shape 的 `Gems Speedup` / `TFLOPS`。主判据：opt 的 Speedup 要明显大于 orig。
7. 归档：收益成立的样例写到 `results/<op>/`，含配对理由、编译器保守性归因（可结合 `.dump` 佐证）、源码 diff、正确性结果、标注 GPU index 与 harness 轨道的 A/B 数据。

## 常用命令

准备干净环境（会 `rm -rf FlagGems-opt`，清空未归档改动，只在开新样例时用）：

```bash
/path/to/flaggems-pass-opt/scripts/pass.sh restart
```

跑一个算子的 orig/opt A/B（自动选空闲卡）：

```bash
/path/to/flaggems-pass-opt/scripts/pass.sh test -g <op> -c auto
```

改了 FlagTree 编译器本身后重装 flagtree：

```bash
/path/to/flaggems-pass-opt/scripts/pass.sh reinstall
```

## 注意事项

- `pass.sh restart` 会删除并重建 `FlagGems-opt`，清空所有未归档改动——正在迭代当前样例时不要跑它。
- A/B 必须跑在空闲 GPU 上，否则结果会抖动 3-4 倍，数据不可信。
- 一次只落一个 Pass / 一个算子，保持 diff 可读、可归因。
- 所有改写必须是等价变换，不改变数值结果；正确性未 100% 通过不许进性能测试。
- 归档数据务必标注 GPU index 与 harness 轨道（仓库轨 / 裸 kernel 轨），否则不可复现。
- `pass.sh test` 依赖 `/root/pass/diff/<op>.diff` 存在（opt 轨会 `git apply` 它）；脚本内 `BASE_DIR` 硬编码 `/root/pass`，换工作区需同步修改。
