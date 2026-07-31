"""
Write request and response data to per-session JSONL files.

Captures HTTP request/response pairs for the Anthropic Messages API
(/v1/messages) via mitmproxy.  Requests are grouped into sessions using
the ``x-session-affinity`` request header.  SSE streaming responses are
automatically reassembled into complete Messages API response objects.

Output directory is controlled by MITMPROXY_OUTDIR (default: "sessions").
Each session file is named  session_<name>.jsonl  and contains one JSON
line per turn: {"request": ..., "response": ..., ...}
"""

import json
import os
import re
from typing import TextIO, Dict, Any, List

from mitmproxy import http


def reassemble_sse_to_message(sse_text: str) -> Dict[str, Any]:
    """
    Reassemble an SSE stream into a complete Anthropic Messages API response.

    Parses streaming events (message_start, content_block_start/delta/stop,
    message_delta, message_stop) and reconstructs the equivalent non-streaming
    response object:

        {
          "id": "msg_...",
          "type": "message",
          "role": "assistant",
          "model": "...",
          "content": [ {type: "text", text: "..."}, {type: "tool_use", ...} ],
          "stop_reason": "end_turn",
          "usage": { ... }
        }
    """
    message: Dict[str, Any] = {}
    content_blocks: Dict[int, Dict[str, Any]] = {}  # index -> block
    tool_json_fragments: Dict[int, List[str]] = {}   # index -> json parts

    event_blocks = re.split(r"\n\nevent:", sse_text.strip())

    for i, block in enumerate(event_blocks):
        if i > 0:
            block = "event:" + block
        block = block.strip()
        if not block:
            continue

        event_type = None
        data_json = None
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_json = line[5:].strip()

        if not (event_type and data_json):
            continue
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError:
            continue

        # --- message_start: seed the top-level message fields ---
        if event_type == "message_start" and isinstance(data, dict):
            msg = data.get("message", {})
            if isinstance(msg, dict):
                message = {
                    "id": msg.get("id"),
                    "type": msg.get("type", "message"),
                    "role": msg.get("role", "assistant"),
                    "model": msg.get("model"),
                    "stop_reason": msg.get("stop_reason"),
                    "stop_sequence": msg.get("stop_sequence"),
                    "usage": msg.get("usage", {}),
                }

        # --- content_block_start ---
        elif event_type == "content_block_start" and isinstance(data, dict):
            idx = data.get("index", 0)
            cb = data.get("content_block", {})
            if isinstance(cb, dict):
                block_type = cb.get("type")
                if block_type == "text":
                    content_blocks[idx] = {"type": "text", "text": cb.get("text", "")}
                elif block_type == "tool_use":
                    content_blocks[idx] = {
                        "type": "tool_use",
                        "id": cb.get("id"),
                        "name": cb.get("name"),
                        "input": {},
                    }
                    tool_json_fragments[idx] = []
                elif block_type == "thinking":
                    content_blocks[idx] = {"type": "thinking", "thinking": cb.get("thinking", "")}
                else:
                    content_blocks[idx] = dict(cb)

        # --- content_block_delta ---
        elif event_type == "content_block_delta" and isinstance(data, dict):
            idx = data.get("index", 0)
            delta = data.get("delta", {})
            if isinstance(delta, dict):
                delta_type = delta.get("type")
                if delta_type == "text_delta" and idx in content_blocks:
                    content_blocks[idx]["text"] += delta.get("text", "")
                elif delta_type == "thinking_delta" and idx in content_blocks:
                    content_blocks[idx]["thinking"] += delta.get("thinking", "")
                elif delta_type == "input_json_delta" and idx in tool_json_fragments:
                    tool_json_fragments[idx].append(delta.get("partial_json", ""))

        # --- content_block_stop: finalize tool_use input ---
        elif event_type == "content_block_stop" and isinstance(data, dict):
            idx = data.get("index", 0)
            if idx in tool_json_fragments and idx in content_blocks:
                raw = "".join(tool_json_fragments[idx])
                try:
                    content_blocks[idx]["input"] = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    content_blocks[idx]["input"] = raw
                    content_blocks[idx]["_input_parse_error"] = True
                del tool_json_fragments[idx]

        # --- message_delta: stop_reason / final usage ---
        elif event_type == "message_delta" and isinstance(data, dict):
            delta = data.get("delta", {})
            if isinstance(delta, dict):
                if "stop_reason" in delta:
                    message["stop_reason"] = delta["stop_reason"]
                if "stop_sequence" in delta:
                    message["stop_sequence"] = delta["stop_sequence"]
            usage = data.get("usage")
            if isinstance(usage, dict):
                message.setdefault("usage", {}).update(usage)

    # Assemble final content list in index order
    message["content"] = [
        content_blocks[idx] for idx in sorted(content_blocks.keys())
    ]
    return message


# ---------------------------------------------------------------------------
# Session-grouped writer
# ---------------------------------------------------------------------------


class JSONLWriter:
    def __init__(self) -> None:
        self.output_dir = os.getenv("MITMPROXY_OUTDIR", "sessions_cc")
        os.makedirs(self.output_dir, exist_ok=True)

        self.session_files: Dict[str, TextIO] = {}          # session_name -> file
        self.pending_requests: Dict[str, Dict[str, Any]] = {}  # flow_id -> request_data
        self.flow_session: Dict[str, str] = {}               # flow_id -> session_name
        self.streaming_buffers: Dict[str, List[bytes]] = {}  # flow_id -> chunks

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_content(content: bytes) -> str:
        """Decode bytes preferring UTF-8 over mitmproxy's default Latin-1."""
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("latin-1")

    @staticmethod
    def _is_messages_api(flow: http.HTTPFlow) -> bool:
        return "/v1/messages" in flow.request.pretty_url or "anthropic/messsages" in flow.request.pretty_url or "/v1/messages?beta=true" in flow.request.pretty_url

    def _get_session_file(self, session_name: str) -> TextIO:
        """Return (and lazily open) the JSONL file for *session_name*."""
        if session_name not in self.session_files:
            # Sanitize for use as filename
            safe = re.sub(r"[^\w\-.]", "_", session_name)
            filepath = os.path.join(self.output_dir, f"session_{safe}.jsonl")
            self.session_files[session_name] = open(filepath, "a", encoding="utf-8")
        return self.session_files[session_name]

    # ------------------------------------------------------------------
    # mitmproxy hooks
    # ------------------------------------------------------------------

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        """Enable streaming for SSE responses so thinking tokens pass through
        immediately instead of being buffered until the response completes.

        Uses a stream callable (mitmproxy 10+) to capture each chunk while
        forwarding it unmodified to the client.
        """
        if not self._is_messages_api(flow):
            return
        content_type = flow.response.headers.get("content-type", "").lower()
        if "text/event-stream" in content_type:
            buf: List[bytes] = []
            self.streaming_buffers[flow.id] = buf

            def _capture_and_forward(chunk: bytes) -> bytes:
                if chunk:
                    buf.append(chunk)
                return chunk

            flow.response.stream = _capture_and_forward

    def request(self, flow: http.HTTPFlow) -> None:
        if not self._is_messages_api(flow):
            return
        try:
            session_name = flow.request.headers.get("x-claude-code-session-id", "unknown")
            self.flow_session[flow.id] = session_name

            body: Dict[str, Any] = {}
            if flow.request.content:
                content_type = flow.request.headers.get("content-type", "").lower()
                if "application/json" in content_type:
                    try:
                        body = json.loads(flow.request.content.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

            self.pending_requests[flow.id] = {
                "method": flow.request.method,
                "url": flow.request.pretty_url,
                "headers": dict(flow.request.headers),
                "timestamp": flow.request.timestamp_start,
                "body": body,
            }

        except Exception as e:
            self.pending_requests[flow.id] = {
                "error": f"Failed to process request: {e}",
                "url": getattr(flow.request, "pretty_url", "unknown"),
                "method": getattr(flow.request, "method", "unknown"),
                "timestamp": getattr(flow.request, "timestamp_start", None),
            }

    def response(self, flow: http.HTTPFlow) -> None:
        if not self._is_messages_api(flow):
            return

        session_id = self.flow_session.pop(flow.id, None)
        request_data = self.pending_requests.pop(flow.id, None)

        try:
            if request_data is None:
                request_data = {
                    "method": getattr(flow.request, "method", "unknown"),
                    "url": getattr(flow.request, "pretty_url", "unknown"),
                    "timestamp": getattr(flow.request, "timestamp_start", None),
                }

            # --- Build response body ---
            response_body: Any = None

            # Check if this was a streamed response (content not available)
            streamed_chunks = self.streaming_buffers.pop(flow.id, None)

            if streamed_chunks is not None:
                # Response was streamed — reassemble from collected chunks,
                # falling back to flow.response.content if available.
                raw = b"".join(streamed_chunks) if streamed_chunks else (flow.response.content or b"")
                if raw:
                    sse_text = self._decode_content(raw)
                    try:
                        response_body = reassemble_sse_to_message(sse_text)
                    except Exception:
                        response_body = sse_text
                else:
                    response_body = {"_streamed": True, "_note": "SSE response was streamed through proxy"}

            elif flow.response.content:
                content_type = flow.response.headers.get("content-type", "").lower()

                if "application/json" in content_type:
                    try:
                        response_body = json.loads(
                            flow.response.content.decode("utf-8")
                        )
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        response_body = self._decode_content(flow.response.content)

                elif "text/event-stream" in content_type:
                    sse_text = self._decode_content(flow.response.content)
                    try:
                        response_body = reassemble_sse_to_message(sse_text)
                    except Exception:
                        response_body = sse_text

                else:
                    response_body = self._decode_content(flow.response.content)

            # --- Write turn to session file ---
            turn_data = {
                "request": request_data.get("body"),
                "response": response_body,
                "flow_id": flow.id,
                "duration": (flow.response.timestamp_end or 0)
                - (flow.request.timestamp_start or 0),
            }

            session_name = session_id or "unknown"
            out = self._get_session_file(session_name)
            json_line = json.dumps(turn_data, ensure_ascii=False, separators=(",", ":"))
            out.write(json_line + "\n")
            out.flush()

        except Exception as e:
            error_data = {
                "error": f"Failed to process response: {e}",
                "flow_id": flow.id,
                "url": getattr(flow.request, "pretty_url", "unknown"),
                "method": getattr(flow.request, "method", "unknown"),
                "timestamp": getattr(flow.response, "timestamp_end", None),
            }
            session_name = session_id or "unknown"
            out = self._get_session_file(session_name)
            json_line = json.dumps(error_data, ensure_ascii=False, separators=(",", ":"))
            out.write(json_line + "\n")
            out.flush()

    def done(self):
        # Write incomplete requests to their session files
        for flow_id, request_data in self.pending_requests.items():
            session_name = self.flow_session.get(flow_id, "unknown")
            incomplete = {
                "request": request_data.get("body"),
                "response": None,
                "flow_id": flow_id,
                "incomplete": True,
                "error": "Response not received before shutdown",
            }
            try:
                out = self._get_session_file(session_name)
                json_line = json.dumps(
                    incomplete, ensure_ascii=False, separators=(",", ":")
                )
                out.write(json_line + "\n")
                out.flush()
            except Exception:
                pass

        self.pending_requests.clear()
        self.flow_session.clear()

        # Close all session files
        for f in self.session_files.values():
            if not f.closed:
                f.close()
        self.session_files.clear()


addons = [JSONLWriter()]
