---
name: flaggems-pass-opt
description: >
  This skill should be used when running the compiler-pass-driven FlagGems operator
  optimization loop — i.e. when the user mentions "跑优化循环", "A/B benchmark",
  "pass 优化", "编译器 pass", "LICM", "强度削减", "选算子", "算子优化", "FlagGems-opt",
  "pass.sh", or asks to pick a pass+operator pair, apply an optimization to
  FlagGems-opt, run the orig/opt benchmark harness, or archive a successful sample.
  It encodes the full 阶段 0–4 workflow: prepare clean env, pair a compiler pass with
  an operator, hand-apply the optimization, measure correctness + A/B performance,
  and archive results. 全程用中文回答。
---

# FlagGems 编译器 Pass 驱动优化 Skill

把 FlagTree 编译器的优化 Pass（见 `/root/pass/pass清单.md` 与 `/root/pass/pass源码级总结.md`）当成一份**人工优化清单**，在 FlagGems **算子源码层**逐条核对、手动落地。

核心论据：编译器的 Pass 是保守的，而我们在源码层拥有完整语义，能把这些优化做得更彻底，并按编译器优化的 pattern 组织代码，保证不漏掉机会。

每个样例最终交付：**用了哪个 Pass + 源码 diff + 正确性 100% 通过 + 标注了 GPU/harness 的 A/B 性能数据**。目标：形成一篇顶会论文工作。

> 语言要求：全程用中文回答。目录约定与铁律见 `/root/pass/CLAUDE.md`。

## 统一入口 `pass.sh`

脚本随 skill 一起分发，位于本 skill 的 `scripts/pass.sh`。调用时先设个别名：

```bash
PASS="$(dirname "$(find /root/.claude/skills/flaggems-pass-opt -name pass.sh)")/pass.sh"
# 或直接用完整路径 /root/.claude/skills/flaggems-pass-opt/scripts/pass.sh
```

所有环境操作走它的子命令（下文为简洁写作 `pass.sh`）：

| 子命令 | 作用 |
|---|---|
| `pass.sh gpu` | 扫描并锁定最闲置 GPU，回显 index |
| `pass.sh reinstall` | `FlagTree` git pull 后重装 flagtree（改了编译器本身后用） |
| `pass.sh restart` | `FlagGems` git pull 后 `rm -rf` 旧的、`cp -r` 出干净的 `FlagGems-opt` |
| `pass.sh test -g <op> [-c <dev\|auto>]` | A/B harness：orig/opt 各 uninstall → install -e → 带 `MLIR_ENABLE_DUMP=1` 跑 pytest benchmark |
| `pass.sh all -g <op> [-c <dev\|auto>]` | `restart` + `test` 一条龙 |

`-c` 省略或传 `auto` 时自动挑最闲置卡。

## 阶段 0 —— 准备干净环境

```bash
cd /root/pass
PASS=/root/.claude/skills/flaggems-pass-opt/scripts/pass.sh
"$PASS" restart   # 拉取最新 FlagGems 基线，删掉旧的 FlagGems-opt，复制出干净副本
```

> **注意**：`pass.sh restart` 会 `rm -rf FlagGems-opt` 后重新 `cp -r`，**清空所有未归档改动**。
> 只在开新样例、想从干净基线重来时运行；正在迭代当前样例时**不要**跑它。
> 改动了 FlagTree 编译器本身，用 `"$PASS" reinstall` 重装 flagtree 后再测。

确认 GPU：A/B 必须跑在**空闲卡**上，否则被其他租户占用会让结果抖动 3-4 倍。

```bash
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv
```

挑一张 `memory.used` 接近 0、`utilization` 为 0 的卡，用 `-c <index>` 传给 `pass.sh test`（或用 `pass.sh test -c auto` 自动选卡）。

## 阶段 1 —— 选 Pass + 选算子（配对）

### 1.1 选 Pass
从 `/root/pass/pass源码级总结.md` 里挑**优化逻辑能在源码层手工复现**的 Pass。

### 1.2 选算子（按 Pass 的 pattern 匹配，用搜索工具，不要靠记忆）

```bash
cd /root/pass/FlagGems/src/flag_gems/ops
# LICM：带 range 循环、循环体里重复算 mask/指针的 kernel
grep -rln "for .* in range" . --include=*.py
# Canonicalizer / 强度削减：libdevice 的 pow、重复平方
grep -rln "pow(" . --include=*.py
```

### 1.3 关键校验 —— benchmark 必须真的会跑
打开 `benchmark/test_<op>.py` 确认：

1. **没有被 `skipif` 跳过**。例如 `scaled_softmax` 带 `@pytest.mark.skipif(TE_AVAILABLE is False ...)`，必须先确认 `transformer_engine` 已安装，否则整组 skip，A/B 没意义。
2. **不是访存受限（memory-bound）的纯逐点算子**。gelu 这类访存占满带宽，ALU 层面的节省会被噪声淹没。**优先选带归约循环 / 计算密度高的算子**（softmax backward、norm、各类 reduce）。

### 1.4 写下配对理由
记录：选了哪个 Pass、哪个算子、**编译器为什么保守不触发这个优化**（方法论核心论据）。

## 阶段 2 —— 在 FlagGems-opt 实现优化

只改 `FlagGems-opt/`，逐个 kernel 落地：

- 严格按 Pass 语义改写，**不改变数值结果**（强度削减、外提、消重都是等价变换）。
- diff 里加注释：用了哪个 Pass、为什么编译器不做、源码层为什么能做（参考已有 `gelu.py` 的注释风格）。
- 一次只落一个 Pass / 一个算子，保持 diff 可读、可归因。

**LICM 落地模板**（以 K-block 循环为例）：把每次迭代都重算、但与 `k_block_idx` 无关的量（如 `row_mask = query_mask[:, None]`、指针基址 `xxx_row_ptr[:, None]`）提到循环外，循环内只保留真正依赖迭代变量的部分。

## 阶段 3 —— 测量（双轨，都跑在空闲 GPU 上）

### 3.1 正确性（硬门槛，必须先过）

```bash
cd /root/pass/FlagGems-opt
CUDA_VISIBLE_DEVICES=<idle_gpu> pytest tests/test_<op>.py -s
```

必须 **100% 通过**。不过就回阶段 2 修，**不要进性能测试**。

### 3.2 性能 · 仓库轨（端到端，收益主证据）

```bash
cd /root/pass
/root/.claude/skills/flaggems-pass-opt/scripts/pass.sh test -g <op> -c <idle_gpu>
```

`pass.sh test` 对两套代码各做一遍 `pip uninstall flag_gems` → `pip install -e .` → 清 `~/.triton/cache` → 跑 benchmark。其中 `MLIR_ENABLE_DUMP=1` 那次用 `pytest benchmark/test_<op>.py -s -x --level core --dtypes float16 --warmup 0 --iter 1`（只跑 float16、单次、不预热，dump 输出到 stderr，stdout 丢弃），随后另起一次不带 `MLIR_ENABLE_DUMP` 的正常 `pytest ... -s -x` 跑出 benchmark 结果。产物写到 `logs/<op>/`：

- `orig.benchmark` / `opt.benchmark` —— stdout，benchmark 结果（对比看这两个）
- `orig.dump` / `opt.dump` —— stderr，`MLIR_ENABLE_DUMP` 的各 Pass 前后 IR
- `changes.diff` —— opt 相对基线的 `git diff` 快照

对比两份 `.benchmark` 里**同一 shape** 的 `Gems Latency` / `Gems Speedup` / `TFLOPS`。**主判据：opt 的 `Gems Speedup` 要明显大于 orig（不是噪声级别的"稍大于"）。** 需确认某个 Pass 是否真触发时，去 `.dump` 搜对应 IR 变化佐证。

### 3.3 性能 · 可靠轨（裸 kernel A/B，可选，用于噪声大的算子）
对 gelu 这种 memory-bound、仓库轨噪声大的算子，另写裸 kernel A/B harness：同一份输入分别调 orig / opt kernel，固定在空闲卡上多次计时取中位数。此类算子仓库轨数据仅作参考。

## 阶段 4 —— 归档文档（写到 `results/<op>/`）

成功样例在 `results/<op>/` 下建子目录归档（可拆成多份 md，如 `single_pass.md` 记单个 Pass 落地、`compiler_feedback.md` 记从 `.dump` 反推的编译器行为）：

1. **配对**：用了哪个 Pass、哪个算子。
2. **归因**：编译器为什么保守 / 不触发（可结合 `logs/<op>/*.dump` 的 IR 佐证）。
3. **源码 diff**：见 `logs/<op>/changes.diff`。
4. **正确性**：`pytest tests/test_<op>.py` 结果（必须 100% pass）。
5. **性能**：A/B 数据，**务必标注 GPU index 与 harness（仓库轨 / 裸 kernel 轨）**，否则不可复现。重点对比 `orig.benchmark` vs `opt.benchmark` 的 `Gems Speedup`。

## 速查：一次完整循环

```
1. 读 pass 文档 + FlagGems 算子源码（FlagGems/src/flag_gems/ops/），选一个理论上讲得通的 Pass+算子配对。
2. （按需）pass.sh restart 生成干净的 FlagGems-opt，在其上改。
3. 阶段 3.1 过正确性 → pass.sh test 跑仓库轨 benchmark。
4. 读 logs/<op>/*.benchmark：若 opt 的 Gems Speedup 明显大于 orig，在 results/<op>/ 写文档。
5. 大概率一次找不到有效优化 —— 重复本循环，拿到一个好结果。
```
