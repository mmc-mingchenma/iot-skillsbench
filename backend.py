"""
IoT-Agent-Backend adapter: run the SkillsBench LangGraph in a subprocess worker.

Implements the same session protocol as IoT-Agent-LangGraph (duck-typed).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Any, AsyncGenerator, List

from src.config import AppConfig, load_config
from scripts.run_task_single import run_single_task as single_run_task

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent


def _read_workspace_skillsbench_config(workspace_path: Path) -> dict[str, Any]:
    cfg_path = Path(workspace_path) / "dev" / "skillsbench_config.json"
    if not cfg_path.is_file():
        return {}
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _skills_dir_from_profile(profile: str | None) -> str | None:
    p = (profile or "").strip().lower()
    # Support both legacy short names and the new @iot-skillsbench/ prefix format.
    if p in ("skills-human-expert", "@iot-skillsbench/skills-human-expert"):
        return str(_REPO_ROOT / "skills-human-expert")
    if p in ("skills-llm-generated", "@iot-skillsbench/skills-llm-generated"):
        return str(_REPO_ROOT / "skills-llm-generated")
    if p == "none":
        return None
    return None


def _api_base_from_model_platform(model_platform: str | None) -> str:
    """
    Pick an API base URL for model calls.

    Priority:
    - OPENAI_BASE_URL env (lets Backend control routing)
    - known defaults by model_platform
    """
    mp = (model_platform or "").strip().lower()
    # SkillsBench requirement: for OpenRouter mode, prefer LAB_API_BASE
    # (backend-controlled endpoint), then OPENAI_BASE_URL, then official default.
    if mp in ("openrouter",):
        lab_base = (os.environ.get("LAB_API_BASE") or "").strip()
        if lab_base:
            return lab_base
        env_base = (os.environ.get("OPENAI_BASE_URL") or "").strip()
        if env_base:
            return env_base
        return "https://openrouter.ai/api/v1"

    env_base = (os.environ.get("OPENAI_BASE_URL") or "").strip()
    if env_base:
        return env_base

    if mp in ("openai", "chatgpt"):
        return "https://api.openai.com/v1"
    # Fallback to OpenAI-compatible default (many gateways accept this shape)
    return "https://api.openai.com/v1"


def _build_project_output_dir(workspace_path: Path, config: AppConfig) -> Path:
    """
    Use project workspace root directly as generation base directory.
    """
    return Path(workspace_path)


def _merge_tree(src: Path, dst: Path) -> None:
    """Merge src directory tree into dst, replacing existing files."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _merge_tree(item, target)
            if item.exists():
                item.rmdir()
        else:
            if target.exists():
                target.unlink()
            shutil.move(str(item), str(target))


def _flatten_output_into_root(run_dir: Path) -> None:
    """
    Move run_dir/output/* into run_dir and remove output folder.
    This keeps integration output at the project root as requested.
    """
    output_dir = run_dir / "output"
    if not output_dir.is_dir():
        return
    for item in output_dir.iterdir():
        target = run_dir / item.name
        if item.is_dir():
            _merge_tree(item, target)
        else:
            if target.exists():
                target.unlink()
            shutil.move(str(item), str(target))
    shutil.rmtree(output_dir, ignore_errors=True)


def _flatten_run_dir_into_parent(run_dir: Path, parent_dir: Path) -> None:
    """
    Move run_dir/* into parent_dir and remove run_dir.
    This flattens task folder (e.g. `chat/`) into project root.
    """
    run_dir = Path(run_dir)
    parent_dir = Path(parent_dir)
    if not run_dir.is_dir():
        return
    if run_dir.resolve() == parent_dir.resolve():
        return
    parent_dir.mkdir(parents=True, exist_ok=True)
    for item in run_dir.iterdir():
        target = parent_dir / item.name
        if item.is_dir():
            _merge_tree(item, target)
        else:
            if target.exists():
                target.unlink()
            shutil.move(str(item), str(target))
    shutil.rmtree(run_dir, ignore_errors=True)


class SkillsBenchSession:
    """Runs SkillsBench once per user message; outputs under project workspace."""

    def __init__(
        self,
        session_id: str,
        project_id: str,
        workspace_path: Path,
        workspace_registry: Any,
        model_platform: str,
        model_type: str,
        platform: str,
    ) -> None:
        self._session_id = session_id
        self._project_id = project_id
        self._workspace_path = Path(workspace_path).resolve()
        self._workspace_registry = workspace_registry
        # Hard guard: this backend always uses OpenRouter routing.
        self._model_platform = "openrouter"
        self._model_type = model_type
        self._platform = platform
        self._config: AppConfig = load_config(_REPO_ROOT / "config.yaml")
        # Override repo config.yaml with per-project template config (align with scripts/batch_run.py).
        ws_cfg = _read_workspace_skillsbench_config(self._workspace_path)
        sb_board = ws_cfg.get("board")
        sb_framework = ws_cfg.get("framework")
        sb_profile = ws_cfg.get("skills_profile")
        skills_dir = _skills_dir_from_profile(sb_profile)
        use_skills = bool(skills_dir)
        try:
            from dataclasses import replace

            self._config = replace(
                self._config,
                input=replace(
                    self._config.input,
                    board=sb_board or self._config.input.board,
                    framework=sb_framework or self._config.input.framework,
                ),
                model=replace(
                    self._config.model,
                    name=((self._model_type or "").strip() or self._config.model.name),
                    api_base=_api_base_from_model_platform(self._model_platform),
                    api_key_env=(
                        "LAB_API_KEY"
                        if (self._model_platform or "").strip().lower() == "openrouter"
                        else self._config.model.api_key_env
                    ),
                ),
                graph=replace(
                    self._config.graph,
                    use_skills=use_skills,
                    skills_dir=skills_dir or self._config.graph.skills_dir,
                ),
            )
        except Exception:
            pass
        self._history: List[dict] = []
        self._is_processing = False
        self._cancel_event = threading.Event()
        # Interactive draft mode: collect requirements until user explicitly runs.
        self._draft_requirements: List[str] = []

    def _draft_text(self) -> str:
        return "\n\n".join([s for s in self._draft_requirements if s.strip()]).strip()

    def _infer_hints(self, text: str) -> dict[str, Any]:
        """
        Lightweight heuristic extraction for interactive clarification.
        Intentionally avoids any model calls.
        """
        t = text.lower()
        hints: dict[str, Any] = {}

        # Boards / framework hints
        if any(k in t for k in ("esp32", "esp-idf", "espidf", "idf.py")):
            hints["platform"] = "ESP-IDF"
        if "zephyr" in t:
            hints["platform"] = "Zephyr"
        if any(k in t for k in ("arduino", ".ino", "mega 2560", "uno", "nano")):
            hints["platform"] = "Arduino"

        # Connectivity
        if "wifi" in t or "802.11" in t:
            hints["connectivity"] = (hints.get("connectivity") or []) + ["Wi‑Fi"]
        if "ble" in t or "bluetooth" in t:
            hints["connectivity"] = (hints.get("connectivity") or []) + ["BLE"]
        if "mqtt" in t:
            hints["protocols"] = (hints.get("protocols") or []) + ["MQTT"]
        if "http" in t or "rest" in t:
            hints["protocols"] = (hints.get("protocols") or []) + ["HTTP"]

        # Timing / rates
        rate = re.findall(r"(\d+(?:\.\d+)?)\s*(hz|khz|mhz)\b", t)
        if rate:
            hints["rates"] = [f"{v}{u}" for v, u in rate[:6]]
        every = re.findall(r"every\s+(\d+(?:\.\d+)?)\s*(ms|s|sec|seconds|minutes|min)\b", t)
        if every:
            hints["intervals"] = [f"every {v} {u}" for v, u in every[:6]]

        # Common peripherals keywords (non-exhaustive)
        peripherals = []
        for k in (
            "lcd1602",
            "mpu6050",
            "dht11",
            "ds18b20",
            "ds1307",
            "ultrasonic",
            "hc-sr04",
            "joystick",
            "button",
            "buzzer",
            "servo",
            "led",
            "relay",
            "microphone",
        ):
            if k in t:
                peripherals.append(k.upper() if k.isalnum() else k)
        if peripherals:
            hints["peripherals"] = sorted(set(peripherals))[:12]

        # Pins: very loose detection
        pins = re.findall(r"\b(d\d{1,2}|a\d{1,2}|gpio\d{1,2})\b", t, flags=re.IGNORECASE)
        if pins:
            hints["pins"] = sorted(set(p.upper() for p in pins))[:20]

        return hints

    def _build_interactive_reply(self, last_user_text: str) -> str:
        draft = self._draft_text()
        hints = self._infer_hints(draft + "\n" + (last_user_text or ""))
        lines: List[str] = []
        lines.append("Recorded.")
        lines.append("")
        lines.append(f"Draft items: {len([s for s in self._draft_requirements if s.strip()])}")
        if last_user_text.strip():
            preview = last_user_text.strip().replace("\n", " ")
            if len(preview) > 140:
                preview = preview[:137] + "..."
            lines.append(f"Last: {preview}")

        if hints:
            lines.append("")
            lines.append("Detected hints:")
            if "platform" in hints:
                lines.append(f"- Platform: {hints['platform']}")
            if "peripherals" in hints:
                lines.append(f"- Peripherals: {', '.join(hints['peripherals'])}")
            if "pins" in hints:
                lines.append(f"- Pins: {', '.join(hints['pins'])}")
            if "connectivity" in hints:
                lines.append(f"- Connectivity: {', '.join(hints['connectivity'])}")
            if "protocols" in hints:
                lines.append(f"- Protocols: {', '.join(hints['protocols'])}")
            if "rates" in hints:
                lines.append(f"- Rates: {', '.join(hints['rates'])}")
            if "intervals" in hints:
                lines.append(f"- Timing: {', '.join(hints['intervals'])}")

        # Targeted questions (heuristics)
        questions: List[str] = []
        if "peripherals" not in hints:
            questions.append("Which peripherals/sensors/actuators are involved?")
        if "platform" not in hints:
            questions.append("Which framework should we target (Arduino / ESP‑IDF / Zephyr)?")
        if "pins" not in hints:
            questions.append("Any fixed pin assignments (GPIO/D/A pins) or should we choose defaults?")
        if "intervals" not in hints and "rates" not in hints:
            questions.append("What sampling/update rate is required (e.g. every 200ms / 10Hz)?")
        questions = questions[:4]

        if questions:
            lines.append("")
            lines.append("Quick questions:")
            for q in questions:
                lines.append(f"- {q}")

        lines.append("")
        lines.append("Commands: `/show` to review draft, `/clear` to reset, `/run` to generate artifacts.")
        return "\n".join(lines)

    @property
    def is_processing(self) -> bool:
        return self._is_processing

    def cancel(self) -> bool:
        if self._is_processing:
            self._cancel_event.set()
            return True
        return False

    def get_history(self) -> list:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()
        self._draft_requirements.clear()

    async def process_message(self, content: str) -> AsyncGenerator[dict, None]:
        self._is_processing = True
        self._cancel_event.clear()
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()

        text = (content or "").strip()
        lower = text.lower()

        # ------------------------------------------------------------
        # Interactive mode: collect requirements until explicit /run
        # ------------------------------------------------------------
        if lower in ("/help", "help"):
            msg = (
                "IoT-SkillsBench interactive mode:\n"
                "- Send requirements normally to build up a draft.\n"
                "- Send `/run` to generate artifacts using the current draft.\n"
                "- Send `/clear` to clear the draft.\n"
                "- Send `/show` to display the current draft."
            )
            yield {"type": "message", "data": {"content": msg}}
            yield {"type": "done", "data": {"status": "completed"}}
            self._history.append({"role": "user", "content": content})
            self._history.append({"role": "assistant", "content": msg})
            self._is_processing = False
            return

        if lower in ("/clear", "clear"):
            self._draft_requirements.clear()
            msg = "Draft cleared. Send new requirements, then `/run` when ready."
            yield {"type": "message", "data": {"content": msg}}
            yield {"type": "done", "data": {"status": "completed"}}
            self._history.append({"role": "user", "content": content})
            self._history.append({"role": "assistant", "content": msg})
            self._is_processing = False
            return

        if lower in ("/show", "show"):
            draft = "\n\n".join(self._draft_requirements).strip()
            msg = (
                "Current draft requirements:\n\n"
                + (draft if draft else "(empty)\n")
                + "\n\nSend more details, or `/run` to generate."
            )
            yield {"type": "message", "data": {"content": msg}}
            yield {"type": "done", "data": {"status": "completed"}}
            self._history.append({"role": "user", "content": content})
            self._history.append({"role": "assistant", "content": msg})
            self._is_processing = False
            return

        run_requested = lower in ("/run", "run") or lower.startswith("/run ")

        if not run_requested:
            if text:
                self._draft_requirements.append(text)
            msg = self._build_interactive_reply(text)
            yield {"type": "message", "data": {"content": msg}}
            yield {"type": "done", "data": {"status": "completed"}}
            self._history.append({"role": "user", "content": content})
            self._history.append({"role": "assistant", "content": msg})
            self._is_processing = False
            return

        # /run: combine draft into a single requirements string
        combined = self._draft_text()
        if not combined:
            msg = "Draft is empty. Send requirements first, then `/run`."
            yield {"type": "message", "data": {"content": msg}}
            yield {"type": "done", "data": {"status": "completed"}}
            self._history.append({"role": "user", "content": content})
            self._history.append({"role": "assistant", "content": msg})
            self._is_processing = False
            return

        task_id = "chat"
        output_dir = _build_project_output_dir(self._workspace_path, self._config)
        output_dir.mkdir(parents=True, exist_ok=True)

        last_status = ""
        persist_summary = ""
        finished_run_dir = ""
        # Mirror scripts/batch_run.py's visible progress (node names).
        step_map: dict[str, tuple[int, str]] = {
            "manager": (0, "--- Node: manager ---"),
            "pin_mapper": (1, "--- Node: pin_mapper ---"),
            "prepare_workspace": (2, "--- Node: prepare_workspace ---"),
            "coder": (3, "--- Node: coder ---"),
            "assemble_artifacts": (4, "--- Node: assemble_artifacts ---"),
            "persist": (5, "--- Node: persist ---"),
        }
        reached_step = -1

        class _QueueWriter:
            def __init__(self, event_loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
                self._loop = event_loop
                self._queue = queue
                self._buf = ""

            def write(self, data: str) -> int:
                self._buf += data
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    asyncio.run_coroutine_threadsafe(
                        self._queue.put(("line", line)),
                        self._loop,
                    ).result(timeout=120)
                return len(data)

            def flush(self) -> None:
                if not self._buf:
                    return
                line = self._buf
                self._buf = ""
                asyncio.run_coroutine_threadsafe(
                    self._queue.put(("line", line)),
                    self._loop,
                ).result(timeout=120)

        def producer() -> None:
            try:
                if self._cancel_event.is_set():
                    asyncio.run_coroutine_threadsafe(q.put(("cancel",)), loop).result(timeout=120)
                    return

                writer = _QueueWriter(loop, q)
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    # Directly reuse scripts/run_task_single.py execution path.
                    task_file = self._workspace_path / "dev" / "tmp_task.txt"
                    task_file.parent.mkdir(parents=True, exist_ok=True)
                    task_file.write_text(combined, encoding="utf-8")
                    # run_task_single.py takes the same core graph path but raises on failure.
                    run_dir = single_run_task(
                        task_path=task_file,
                        task_name=task_id,
                        task_content=combined,
                        config=self._config,
                        output_dir=output_dir,
                    )
                    run_dir_path = Path(run_dir)
                    _flatten_output_into_root(run_dir_path)
                    _flatten_run_dir_into_parent(run_dir_path, output_dir)
                writer.flush()
                asyncio.run_coroutine_threadsafe(q.put(("end",)), loop).result(timeout=120)
            except Exception as e:  # noqa: BLE001
                logger.exception("SkillsBench stream failed: %s", e)
                asyncio.run_coroutine_threadsafe(q.put(("error", e)), loop).result(timeout=120)

        thread = threading.Thread(target=producer, daemon=True)
        thread.start()

        cancelled = False
        stream_failed = False

        try:
            yield {
                "type": "status",
                "data": {"message": "Running IoT-SkillsBench workflow..."},
            }
            yield {
                "type": "status",
                "data": {"message": f"Output base: {output_dir}"},
            }
            yield {
                "type": "status",
                "data": {
                    "message": (
                        "Model routing: "
                        f"platform={self._model_platform}, "
                        f"api_base={self._config.model.api_base}, "
                        f"api_key_env={self._config.model.api_key_env}, "
                        f"api_key_present={bool((os.environ.get(self._config.model.api_key_env) or '').strip())}"
                    )
                },
            }

            current_node = ""

            while True:
                kind, *rest = await q.get()
                if kind == "cancel":
                    cancelled = True
                    yield {"type": "status", "data": {"message": "Cancelled"}}
                    yield {"type": "done", "data": {"status": "cancelled"}}
                    break
                if kind == "error":
                    err = rest[0] if rest else Exception("unknown")
                    yield {"type": "error", "data": {"message": str(err)}}
                    yield {"type": "done", "data": {"status": "failed"}}
                    stream_failed = True
                    break
                if kind == "end":
                    break

                if kind != "line":
                    continue

                line = str(rest[0] if rest else "").strip()
                if not line:
                    continue

                if line.startswith("--- Node: ") and line.endswith(" ---"):
                    node_name = line.replace("--- Node: ", "", 1).replace(" ---", "", 1).strip()
                    current_node = node_name
                    last_status = f"Node: {node_name}"
                    yield {
                        "type": "status",
                        "data": {"message": last_status},
                    }
                    if node_name in step_map:
                        step, label = step_map[node_name]
                        # avoid spamming duplicates
                        if step > reached_step:
                            reached_step = step
                            yield {
                                "type": "generation_status",
                                "data": {"step": step, "label": label},
                            }
                    continue

                if " complete -> " in line and line.startswith("✅ "):
                    finished_run_dir = line.split(" complete -> ", 1)[-1].strip()
                    continue

                # Emit skills info lines as status events so they appear
                # in the generation log on the Project page.
                #   - "Skills directory: ..." / "Available skills (...)" / "Skill names: ..."
                #     come from loader.py scan_skills() inside the manager node.
                #   - "Project: ..." / "Skills: ..." are printed by run_task_single.py
                #     after the manager node output.
                if (
                    line.startswith("Skills directory:")
                    or line.startswith("Available skills (")
                    or line.startswith("Skill names:")
                    or (
                        current_node == "manager"
                        and (line.startswith("Project:") or line.startswith("Skills:"))
                    )
                ):
                    yield {
                        "type": "status",
                        "data": {"message": line},
                    }
                    continue

                if current_node == "persist":
                    persist_summary = line
                    yield {
                        "type": "message",
                        "data": {"content": persist_summary},
                    }

            if not cancelled and not stream_failed:
                if reached_step < 6:
                    yield {
                        "type": "generation_status",
                        "data": {"step": 6, "label": "Design ready"},
                    }
                yield {"type": "done", "data": {"status": "completed"}}

            self._history.append({"role": "user", "content": content})
            if cancelled:
                assistant_text = "Cancelled."
            elif stream_failed:
                assistant_text = "Run failed."
            elif persist_summary:
                assistant_text = persist_summary
            elif finished_run_dir:
                assistant_text = f"Run finished. Output: `{finished_run_dir}`"
            else:
                assistant_text = f"Run finished. Output base: `{output_dir}`"
            self._history.append({"role": "assistant", "content": assistant_text})
            # Keep draft so user can re-run; do not clear automatically.

        finally:
            self._is_processing = False
            thread.join(timeout=2.0)


def create_skillsbench_session(
    session_id: str,
    project_id: str,
    workspace_path: Path,
    workspace_registry: Any = None,
    model_platform: str = "openai",
    model_type: str = "gpt-4o",
    platform: str = "espidf",
):
    """Factory for IoT-Agent-Backend worker init."""
    return SkillsBenchSession(
        session_id=session_id,
        project_id=project_id,
        workspace_path=workspace_path,
        workspace_registry=workspace_registry,
        model_platform=model_platform,
        model_type=model_type,
        platform=platform,
    )


__all__ = ["create_skillsbench_session", "SkillsBenchSession"]
