# Claude Code 轨迹收集

用 mitmproxy 作为本地代理，坐在 Claude Code 和模型 API 中间，拦截发往 `/v1/messages` 的流量，把每一轮「请求 + 响应」配对写成 JSONL，用于后续分析或训练数据构建。

```text
Claude Code  ──→  mitmproxy（本地代理）  ──→  Anthropic / 模型 API
                       │
                       └─→ 写入 session_<id>.jsonl
```

本目录两个文件：

| 文件 | 说明 |
|------|------|
| [`claude-trace.sh`](./claude-trace.sh) | 启动器：拉起 mitmdump（带引用计数）、注入证书与代理变量、按 profile 启动 claude |
| [`trajectory_writer_cc.py`](./trajectory_writer_cc.py) | mitmproxy addon：拦截 `/v1/messages`、重组 SSE、按 session 分文件写 JSONL |

> ⚠️ 会话数据包含完整请求头（含 API token 等敏感信息）。`sessions/`、`sessions_cc/`、`.mitm_refcount`、`*.jsonl`、`*.log` 已在顶层 `.gitignore` 中排除，不要提交这些运行时产物。

---

## 快速开始

前置一次性准备见下方「安装与证书」。装好后直接用启动器：

```bash
# 默认 settings.json
./claude-trace.sh

# 指定 profile（对应 ~/.claude/settings.zy.json，等价于 cc zy）
./claude-trace.sh zy

# profile 之后的参数透传给 claude
./claude-trace.sh zy --resume
```

启动器行为：

- 第一个参数作为 **profile**，对应 `~/.claude/settings.<profile>.json`，并注入 `IS_SANDBOX=1` 与 `--dangerously-skip-permissions`（与 `~/.bashrc` 里的 `cc` 函数一致）
- 代理变量**只对 claude 进程生效**，不污染当前 shell，也不影响 pip/git 等其他工具
- 自动检测并拉起 mitmdump（默认端口 8181，见脚本顶部 `PROXY_PORT`），输出到本目录 `sessions/`
- **引用计数**（`.mitm_refcount`）：多个终端共享同一个 mitmdump 进程，最后一个退出时才自动关闭，无需手动 `pkill`

使用前按需修改脚本顶部的 `ALLOW_HOSTS`，改成自己的 API 上游域名（正则，点号要转义为 `\.`，如 `kspmas\.ksyun\.com`）。只代理该域名可避免 pip、git 等工具因走代理而证书验证失败。

---

## 安装与证书

### 安装 mitmproxy

需要 Python 3.10+，推荐独立环境避免污染系统 Python。

```bash
pip install mitmproxy      # 或 pipx install mitmproxy（隔离，推荐）
                           # 或 brew install mitmproxy（macOS）
mitmdump --version         # 验证
```

> mitmproxy 套件含三个命令：`mitmproxy`（终端交互界面）、`mitmweb`（浏览器界面）、`mitmdump`（无界面，适合后台静默抓取）。收集轨迹用 `mitmdump` 即可。

### 信任 mitmproxy 证书（关键）

API 流量是 HTTPS 加密的，mitmproxy 需要解密才能记录内容，因此客户端必须信任它的根证书，否则握手失败连不上。

先让 mitmproxy 跑一次生成证书：

```bash
mitmdump      # 看到开始监听后 Ctrl+C 退出即可
```

证书生成在 `~/.mitmproxy/`，其中 `mitmproxy-ca-cert.pem` 就是要用的那张。`claude-trace.sh` 通过 `NODE_EXTRA_CA_CERTS` 指向它——这种方式只对 Claude Code（Node.js）生效，不改动系统全局信任，最安全。

> 一般收集轨迹不需要系统/浏览器全局信任。若确有需要可访问 `http://mitm.it` 按指引安装，但不建议改系统全局信任。

---

## 手动启动（不用启动器时）

调试脚本或临时抓取时可手动跑。开一个终端启动代理：

```bash
export MITMPROXY_OUTDIR=./sessions_cc     # 输出目录，不设则默认 sessions_cc/
mitmdump -s trajectory_writer_cc.py -p 8080 --allow-hosts 'zyapi\.xmsxb\.com'
```

另开一个终端注入环境变量再启动 claude：

```bash
export HTTPS_PROXY=http://127.0.0.1:8080
export HTTP_PROXY=http://127.0.0.1:8080
export NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem
claude
```

结束后停止代理：`pkill -f mitmdump`。

---

## 轨迹格式

每个 session 一个文件 `session_<session_id>.jsonl`，**每行一个 JSON 对象**，对应一次完整的「请求 → 响应」往返（一个 API turn）：

```json
{
  "request":  { ... },   // 发给模型的完整请求体
  "response": { ... },   // 模型这一轮的回复（流式响应已自动重组为完整对象）
  "flow_id":  "uuid",    // 本次往返的唯一标识
  "duration": 121.9      // 本次往返耗时（秒）
}
```

### request 关键字段

请求体是标准 Messages API 格式。`messages` 是核心，每条消息有 `role`（`user` / `assistant`）和 `content`。`content` 可以是字符串或**块数组**，块类型包括：

- `text`：普通文本
- `thinking`：思考内容（带加密 `signature`）
- `tool_use`：模型发起的工具调用（`name` + `input`）
- `tool_result`：工具执行结果（装在 `role: user` 的消息里，但**不是真人输入**）

> **划分「轮次」的要点**：一个用户轮指从真人发一条消息开始、到模型给出最终回复为止；中间可能包含多次工具调用（`tool_use` → `tool_result` → 再 `tool_use` …）。那些 `role: user` 的 `tool_result` 是工具回传，不算新的用户轮。

### response 关键字段

```json
{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "model": "...",
  "stop_reason": "tool_use",     // end_turn=正常结束 / tool_use=要调工具 / max_tokens=被截断
  "usage": {
    "input_tokens": ...,
    "output_tokens": ...,
    "cache_read_input_tokens": ...,       // 命中缓存的 token（多轮下通常很大）
    "cache_creation_input_tokens": ...
  },
  "content": [
    { "type": "thinking", "thinking": "..." },
    { "type": "text", "text": "..." },
    { "type": "tool_use", "name": "...", "input": { ... } }
  ]
}
```

`content` 就是模型这一轮新生成的内容：思考 + 文本 + 工具调用。流式（SSE）响应会被 addon 自动重组成上面这种完整对象，工具调用的分片参数也会拼接还原。

---

## thinking（推理内容）的处理

这是收集和后续使用时最需要注意的一点。

**thinking 出现在哪**

- **response 侧**：模型当前轮生成的 thinking，带完整明文，是最干净、最可用的推理数据。
- **request 侧（messages 历史里）**：历史轮次的 thinking，是否带明文、是否被保留取决于上下文管理策略。

**为什么有的历史 thinking 是空的**

某些请求会配置 `context_management`（如 `clear_thinking`），在多轮中清空历史 thinking 明文以节省上下文，但保留 `signature`（加密签名），于是你会看到：

```json
{ "type": "thinking", "thinking": "", "signature": "Eo4CCm..." }
```

这表示模型当时确实思考过，但明文已被清理、只留签名占位。`thinking == "" 但有 signature` ≠ 模型输出了空思考——它是被清理的历史，应当作**上下文**，不要当成模型的输出内容。

**signature 是什么**

`signature` 是对 thinking 块的加密校验签名，用于向 API 证明这段思考确由模型真实生成。它不是自然语言，做分析或训练时不应当文本使用——只在需要把历史回传给 API 时才需保留。

**不同协议对历史 thinking 的处理不一致**

- 一类做法：**跨用户轮丢弃历史 thinking**（节省上下文），但同一用户轮内多次工具调用的 thinking 全部保留。
- 另一类做法：**要求历史 thinking 必须原样保留并回传**。

分析前先确认这批轨迹来自哪种协议：看 request 里是否有 `context_management` 配置、以及历史 thinking 块是否有明文。

**用于训练时的通用约定**

- **算 loss 的部分**：assistant 当前轮生成的 `thinking` + `text` + `tool_use`。
- **mask 掉（不算 loss）的部分**：`system`、`tools`、所有 `user` 消息、所有 `tool_result`，以及被清空只剩 signature 的历史 thinking。
- **训练与推理必须用同一套模板**：历史 thinking 的保留/清理规则要和上线推理时完全一致，否则会产生训练/推理偏移。

---

## 常见问题排查

- **pip / git 等工具证书报错**：全量代理会让这些工具走 mitmproxy 而证书验证失败。用 `--allow-hosts` 只代理 API 上游域名（脚本里已设 `ALLOW_HOSTS`），其余流量直连。
- **claude 握手失败 / 连不上**：确认 `NODE_EXTRA_CA_CERTS` 指向的证书存在（先手动跑一次 `mitmdump` 生成 `~/.mitmproxy/mitmproxy-ca-cert.pem`）。
- **端口被占用**：改脚本顶部 `PROXY_PORT`，或检查是否已有 mitmdump 在跑（`pgrep -f mitmdump`）。
- **收不到轨迹 / 文件为空**：确认 `ALLOW_HOSTS` 域名与实际 API 上游一致、代理变量已注入到 claude 进程，并查看 `mitmdump.log`。
- **mitmdump 没退出**：`.mitm_refcount` 计数异常时可手动 `pkill -f "mitmdump.*trajectory_writer_cc"` 并删除该文件。

---

## 如何区分主对话与子 agent

### 一个真实例子

真人在 Claude Code 里输入「请你分析今天 minimax 股价」，收集到的文件可能长这样（每行节选开头）：

```text
[1] user: "请你分析今天minimax股价"                                    ← 真人输入，主对话起点
[2] user: "<system-reminder>\nThe following skills are available..."   ← 主对话（注入提醒）
[3] user: "Perform a web search for the query: MiniMax 稀宇科技 股价 今天 2026"
[4] user: "<system-reminder>\nThe following skills are available..."
[5] user: "Perform a web search for the query: MiniMax 00100 港股 最新股价 走势 2026年6月"
[6] user: "Perform a web search for the query: MINIMAX-W 00100.HK 股价 6月 恒生科技指数 纳入"
[7] user: "<system-reminder>..."
```

两类截然不同的开头：

- **真人口语 / 系统注入**（`请你分析今天minimax股价`、`<system-reminder>`）→ 属于**主对话**。
- **干净的英文祈使指令**（`Perform a web search for the query: ...`）→ 是**子 agent** 的任务。主 agent 把「分析股价」拆成多个并行网页搜索，每个由一个子 agent 执行，各带不同搜索词。

关键认知：一个真人请求会在同一个 session 下展开成「1 条主对话 + 多个子 agent」，它们的 request 全部混在同一个文件里。

### 为什么它们在同一个文件里

addon 按 `x-claude-code-session-id` 请求头分文件，而**子 agent 通常沿用主对话的 session id**，因此写进同一个文件。

> 同一个文件 = 同一个顶层 session，但不等于同一条连续对话（context）。一个 session 内部可以包含主对话 context + 若干子 agent context，每个子 agent 有独立的对话历史。

注意 `metadata.user_id` 里的 `session_id` 往往也和主对话相同，**光靠 session_id 区分不了主对话和子 agent**。

### 区分线索（按可靠度）

1. **首条 user 消息的性质**：真人口语（中文、模糊、对话式）或 `<system-reminder>` 开头 → 主对话；干净的英文祈使指令（`Perform a web search for...`、`Analyze the following...`）→ 子 agent 任务。
2. **messages 的连续性（最关键）**：逐行比较 messages 数组。前缀一致、长度逐行递增 → 同一条 context 的连续轮次；messages 很短、从全新指令起头、和前面历史对不上 → 一条新的子 agent context。子 agent 历史独立、从零开始，通常很短；主对话越滚越长。
3. **system 提示与工具集是否突变**：主 agent 是完整 Claude Code system + 几十个工具；子 agent 常是精简 system + 更小工具子集。对比每行 system 文本和 `len(tools)`，突变处往往是子 agent 边界。
4. **主对话 response 里的 Task / Agent 工具调用（因果证据）**：子 agent 由主 agent 用工具派生。若主对话某行 response 里出现 `tool_use` 名为 `Task` / `Agent` / `TaskCreate`，紧随其后的独立指令型 request 就是这个子 agent 在执行。这是把「派生时刻」和「子 agent 请求」对应起来的最硬证据。

---

## 更新记录

- **2026-06-10**：全量代理会导致 pip、git 等工具证书验证失败，需在启动时加 `--allow-hosts` 只代理 API 上游域名。
- **2026-06-18**：修正一键脚本的环境变量设置问题，改为设完环境变量后直接启动 Claude Code。
- 后续：手动脚本整合为 `claude-trace.sh`，默认端口改为 8181，输出目录 `sessions/`，新增引用计数共享 mitmdump 进程。
