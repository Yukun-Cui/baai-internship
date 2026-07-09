#!/usr/bin/env python3
"""
HTTP/1.1 流式反向代理

解决中转 API 服务器 nginx HTTP/2 流式断连问题。
aiohttp 默认使用 HTTP/1.1，避免 HTTP/2 的 GOAWAY/reset 导致 SSE 流中断。

用法:
    python3 proxy.py [port] [upstream_url]

    port:      监听端口，默认 17777
    upstream:  上游地址，默认 https://dm-fox.rjj.cc

示例:
    python3 proxy.py 17777 https://dm-fox.rjj.cc
    python3 proxy.py 8080 https://api.openai.com
"""
import sys
import aiohttp
from aiohttp import web

UPSTREAM = sys.argv[2] if len(sys.argv) > 2 else "https://dm-fox.rjj.cc"
SKIP_REQ = {"host", "transfer-encoding"}
SKIP_RES = {"transfer-encoding"}


async def handler(request: web.Request):
    """透传所有请求到上游，HTTP/1.1 流式回传。"""
    path = request.path_qs
    url = f"{UPSTREAM}{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in SKIP_REQ}
    body = await request.read()

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=600, connect=10, sock_read=600),
    ) as session:
        async with session.request(
            method=request.method, url=url, headers=headers, data=body,
        ) as resp:
            resp_headers = {k: v for k, v in resp.headers.items()
                            if k.lower() not in SKIP_RES}
            r = web.StreamResponse(status=resp.status, headers=resp_headers)
            await r.prepare(request)
            async for chunk in resp.content.iter_chunked(65536):
                await r.write(chunk)
            await r.write_eof()
            return r


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 17777
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    print(f"proxy: http://127.0.0.1:{port} -> {UPSTREAM}")
    web.run_app(app, host="127.0.0.1", port=port, print=lambda *a: None)
