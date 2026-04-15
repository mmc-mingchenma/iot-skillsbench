"""
Worker entrypoint for IoT-Agent-Backend subprocess protocol (JSON lines on stdin/stdout).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

_worker_dir = Path(__file__).resolve().parent
_env_file = _worker_dir / ".env"


def _load_env() -> None:
    if not _env_file.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_file)
        return
    except ImportError:
        pass
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if key and value and not value.startswith("<"):
                    os.environ.setdefault(key, value)


_load_env()

_protocol_stdout = sys.stdout
sys.stdout = sys.stderr

if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))


def _send(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False), file=_protocol_stdout, flush=True)


def _recv() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line.strip())


async def _run() -> None:
    session = None
    while True:
        req = _recv()
        if req is None:
            break
        method = req.get("method")
        if method == "init":
            try:
                from backend import create_skillsbench_session

                session = create_skillsbench_session(
                    session_id=req["session_id"],
                    project_id=req["project_id"],
                    workspace_path=Path(req["workspace_path"]),
                    workspace_registry=None,
                    model_platform=req.get("model_platform", "openai"),
                    model_type=req.get("model_type", "gpt-4o"),
                    platform=req.get("platform", "espidf"),
                )
                _send({"status": "ok"})
            except Exception as e:
                import traceback

                _send({
                    "type": "error",
                    "data": {
                        "message": f"Worker init failed: {e}",
                        "traceback": traceback.format_exc(),
                    },
                })
        elif method == "process_message" and session is not None:
            content = req.get("content", "")
            async for event in session.process_message(content):
                _send(event)
        elif method == "cancel" and session is not None:
            session.cancel()
            _send({"type": "done", "data": {"status": "cancelled"}})
        elif method == "get_history" and session is not None:
            _send({"history": session.get_history()})
        else:
            _send({"type": "error", "data": {"message": "unknown method or session not inited"}})


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
