#!/usr/bin/env python3
"""Automated test script: generate code, build, flash, monitor, then collect pass/fail.

Usage:
    python auto_test.py -i tasks/level3/level3_gpio_specified.txt -t Button_triggered_DHT11_display

Flow:
    1. Run batch_run.py to generate code
    2. idf.py build; on fail -> Compilation Fail, retry (up to 5)
    3. On build success: idf.py flash monitor
    4. After monitor (Ctrl+] to exit): press (f)ail or (s)uccess
    5. On success or 5 failures: print report and exit
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# --- Config: change name for report ---
name = "mingchen"

PROJECT_ROOT = Path(__file__).resolve().parent


def _format_board(board: str) -> str:
    """esp32_s3_box_3 -> Esp32-s3-box-3 (first part capitalized, rest as-is)"""
    parts = board.split("_")
    if parts:
        parts[0] = parts[0].capitalize()
    return "-".join(parts)


def load_config_and_output_dir(config_path: str, output_base: str | None) -> tuple[dict, str]:
    """Load config and compute output_dir the same way batch_run.py does."""
    import yaml
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    board = config.get("input", {}).get("board", "esp32_s3_box_3")
    framework = config.get("input", {}).get("framework", "ESP-IDF")
    use_skills = config.get("graph", {}).get("use_skills", True)
    skills_dir = config.get("graph", {}).get("skills_dir", "skills")
    model_name = config.get("model", {}).get("name", "claude-sonnet-4-5")

    if output_base:
        base_name = output_base
    else:
        base_name = os.path.join("output", f"tasks-{board}-{framework}")

    if use_skills:
        skills_dir_name = os.path.basename(str(skills_dir).rstrip("/"))
        skill_suffix = f"w_skills_{skills_dir_name}"
    else:
        skill_suffix = "wo_skills"

    output_dir = os.path.join(base_name, skill_suffix, model_name)
    return config, output_dir


def find_latest_run_dir(output_dir: str, task_id: str) -> Path | None:
    """Find the latest run directory for a task."""
    runs_dir = Path(output_dir) / task_id / "runs"
    if not runs_dir.exists():
        return None
    subdirs = [d for d in runs_dir.iterdir() if d.is_dir()]
    if not subdirs:
        return None
    latest = max(subdirs, key=lambda p: p.stat().st_mtime)
    return latest / "output"


def run_batch(input_file: str, task_id: str, config_path: str, output_base: str | None) -> bool:
    """Run batch_run.py to generate code. Returns True on success."""
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "batch_run.py"),
        "-i", input_file,
        "-t", task_id,
    ]
    if output_base:
        cmd.extend(["-o", output_base])
    if config_path:
        cmd.extend(["-c", config_path])
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


def run_idf_build(
    output_path: Path,
    idf_setup_cmd: str,
    idf_python: str | None = None,
) -> bool:
    """Run idf.py build in a clean shell (no venv). Returns True on success."""
    # Build env without venv: idf.py must not run under venv
    env = dict(os.environ)
    venv_path = env.pop("VIRTUAL_ENV", None)
    if venv_path and "PATH" in env:
        venv_bin = os.path.join(venv_path, "bin")
        parts = env["PATH"].split(os.pathsep)
        env["PATH"] = os.pathsep.join(p for p in parts if p != venv_bin and venv_bin not in p)

    # Prepend idf_python to PATH so export.sh uses it (e.g. python3.13 for idf5.1_py3.13_env)
    path_prefix = ""
    if idf_python:
        py_path = shutil.which(idf_python, path=env.get("PATH", ""))
        if py_path:
            path_prefix = f'export PATH="{os.path.dirname(py_path)}:$PATH"; '
        else:
            print(f"⚠️  {idf_python} not found in PATH, using default Python")

    shell_cmd = f"{path_prefix}{idf_setup_cmd}; cd {output_path} && idf.py fullclean && idf.py build"
    result = subprocess.run(
        ["/bin/zsh", "-l", "-c", shell_cmd],
        cwd=PROJECT_ROOT,
        env=env,
    )
    return result.returncode == 0


def run_idf_flash_monitor(
    output_path: Path,
    idf_setup_cmd: str,
    idf_python: str | None,
) -> bool:
    """Run idf.py flash then monitor. Monitor runs until user exits (Ctrl+]). Returns True if flash succeeded."""
    env = dict(os.environ)
    venv_path = env.pop("VIRTUAL_ENV", None)
    if venv_path and "PATH" in env:
        venv_bin = os.path.join(venv_path, "bin")
        parts = env["PATH"].split(os.pathsep)
        env["PATH"] = os.pathsep.join(p for p in parts if p != venv_bin and venv_bin not in p)

    path_prefix = ""
    if idf_python:
        py_path = shutil.which(idf_python, path=env.get("PATH", ""))
        if py_path:
            path_prefix = f'export PATH="{os.path.dirname(py_path)}:$PATH"; '

    flash_cmd = f"{path_prefix}{idf_setup_cmd}; cd {output_path} && idf.py flash"
    r = subprocess.run(["/bin/zsh", "-l", "-c", flash_cmd], cwd=PROJECT_ROOT, env=env)
    if r.returncode != 0:
        return False

    monitor_cmd = f"{path_prefix}{idf_setup_cmd}; cd {output_path} && idf.py monitor"
    subprocess.run(["/bin/zsh", "-l", "-c", monitor_cmd], cwd=PROJECT_ROOT, env=env)
    return True


def get_idf_version(idf_setup_cmd: str, idf_python: str | None) -> str:
    """Get ESP-IDF version string, e.g. ESP-IDF v5.1.2"""
    env = dict(os.environ)
    venv_path = env.pop("VIRTUAL_ENV", None)
    if venv_path and "PATH" in env:
        venv_bin = os.path.join(venv_path, "bin")
        parts = env["PATH"].split(os.pathsep)
        env["PATH"] = os.pathsep.join(p for p in parts if p != venv_bin and venv_bin not in p)
    path_prefix = ""
    if idf_python:
        py_path = shutil.which(idf_python, path=env.get("PATH", ""))
        if py_path:
            path_prefix = f'export PATH="{os.path.dirname(py_path)}:$PATH"; '
    cmd = f"{path_prefix}{idf_setup_cmd}; idf.py --version 2>/dev/null"
    out = subprocess.run(
        ["/bin/zsh", "-l", "-c", cmd],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
        timeout=30,
    )
    if out.returncode == 0 and out.stdout:
        m = re.search(r"ESP-IDF\s+v[\d.]+", out.stdout)
        if m:
            return m.group(0)
    return "ESP-IDF v5.1.2"


def print_report(board: str, platform: str, results: list[str]) -> None:
    """Print final report: each attempt as Board, Platform, result (name)"""
    print(f"\n{'='*60}")
    for result in results:
        print(f"{board}, {platform}, {result} ({name})")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Auto test: generate code with batch_run, compile with idf.py (retry on failure)."
    )
    parser.add_argument("-i", "--input", required=True, help="Input task list file")
    parser.add_argument("-t", "--task", required=True, help="Task ID to test")
    parser.add_argument("-c", "--config", default="config.yaml", help="Config file")
    parser.add_argument(
        "-o", "--output",
        default="output/auto_test",
        help="Output base directory (default: output/auto_test)",
    )
    parser.add_argument(
        "--idf-setup",
        default=". $HOME/esp/esp-idf/export.sh",
        help="Command to setup ESP-IDF env (default: . $HOME/esp/esp-idf/export.sh)",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=5,
        help="Max consecutive compile failures before exit (default: 5)",
    )
    parser.add_argument(
        "--idf-python",
        default="python3.13",
        help="Python for ESP-IDF build (default: python3.13). Use '' to disable.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        sys.exit(1)

    config, output_dir = load_config_and_output_dir(args.config, args.output)
    board_str = _format_board(config.get("input", {}).get("board", "esp32_s3_box_3"))
    platform_str = get_idf_version(args.idf_setup, args.idf_python or None)

    task_id = args.task
    fail_count = 0
    results: list[str] = []  # record each attempt for final report

    print(f"📋 Task: {task_id}")
    print(f"📁 Output dir: {output_dir}")
    print(f"🔄 Max consecutive failures: {args.max_failures}")
    print()

    while fail_count < args.max_failures:
        print(f"\n{'='*60}")
        print(f"🚀 Attempt {fail_count + 1} (failures so far: {fail_count})")
        print(f"{'='*60}")

        # Step 1: Generate code
        print("📝 Running batch_run.py ...")
        if not run_batch(str(input_path), task_id, args.config, args.output):
            print("❌ batch_run.py failed")
            results.append("Compilation Fail")
            fail_count += 1
            continue

        # Step 2: Find latest output and build
        out_path = find_latest_run_dir(output_dir, task_id)
        if not out_path or not out_path.exists():
            print(f"❌ No output directory found for {task_id}")
            results.append("Compilation Fail")
            fail_count += 1
            continue

        print(f"📂 Building: {out_path}")
        idf_python = args.idf_python or None
        if not run_idf_build(out_path, args.idf_setup, idf_python):
            print("❌ Compile FAILED")
            results.append("Compilation Fail")
            fail_count += 1
            continue

        print("✅ Compile SUCCESS")
        print("📤 Flashing and starting monitor...")
        if not run_idf_flash_monitor(out_path, args.idf_setup, idf_python):
            print("❌ Flash failed")
            results.append("Compilation Fail")
            fail_count += 1
            continue

        # Monitor exited (user pressed Ctrl+]). Prompt for pass/fail.
        while True:
            choice = input("\nBehavior: (f)ail or (s)uccess? ").strip().lower()
            if choice in ("f", "fail"):
                print("❌ Behavioral Fail")
                results.append("Behavioral Fail")
                fail_count += 1
                break
            if choice in ("s", "success"):
                print("✅ Pass")
                results.append("Pass")
                print_report(board_str, platform_str, results)
                sys.exit(0)
            print("  Please enter 'f' or 's'")

    # 5 consecutive failures
    print_report(board_str, platform_str, results)
    sys.exit(1)


if __name__ == "__main__":
    main()
