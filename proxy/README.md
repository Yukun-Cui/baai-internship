# HTTP/1.1 流式反向代理

解决中转 API 服务的 **nginx HTTP/2 流式断连**问题（`stream disconnected before completion`）。

## 问题背景

Codex CLI 等使用 Rust HTTP 客户端（reqwest）的工具默认走 HTTP/2 连接上游。部分中转服务的 nginx HTTP/2 模块对流式 SSE 长连接不稳定，导致请求发出后 200ms-1.6s 内连接断开。

## 原理

aiohttp 默认使用 **HTTP/1.1**，不触发 HTTP/2 的 GOAWAY/reset 问题，流式连接稳定。

```
Codex ──HTTP──► 127.0.0.1:17777 (aiohttp HTTP/1.1) ──HTTPS/1.1──► 上游
```

## 用法

```bash
# 依赖
pip install aiohttp

# 启动（默认端口 17777，上游 dm-fox.rjj.cc）
python3 proxy.py

# 自定义端口和上游
python3 proxy.py 8080 https://api.openai.com
```

## 配合 Codex CLI

修改 `~/.codex/config.toml`：

```toml
[model_providers.custom]
base_url = "http://127.0.0.1:17777/codex/v1"
```

## 自启动

```bash
# 添加到 ~/.bashrc
if ! pgrep -f "proxy.py" >/dev/null 2>&1; then
    nohup python3 /path/to/proxy.py 17777 &>/tmp/proxy.log &
fi
```
