"""End-to-end eval runner.

For each (eval × mode × run):
  1. Spawn `claude -p` in an isolated tempdir under /tmp.
     - HOME → fresh empty dir (no host ~/.claude/ leak)
     - --strict-mcp-config + --setting-sources "" (no ambient MCPs or settings)
     - .claude/skills/<name> symlink iff mode.skill
     - --mcp-config holds only the chosen MCP servers
  2. Parse the first stream-json event (`system/init`) and assert that loaded
     tools / mcp_servers / skills exactly match the mode's expected state.
  3. Continue parsing the run for tool-call counts, tokens, transcript.
  4. Spawn a second `claude -p` as the grader (prompt embeds
     third_party/skill-creator/agents/grader.md).
  5. Materialize the layout aggregate_benchmark.py expects, then run it.
  6. Append one flat row per successful (eval, mode, run) to the stats output.

Mode encoding: "s<0|1>b<0|1>d<0|1>" — skill, baseten MCP, docs MCP.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import itertools
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

EVAL_ROOT = Path(__file__).resolve().parents[3]
REPO = EVAL_ROOT.parents[1]
SKILL_CREATOR = REPO / "third_party/skill-creator"
GRADER_PROMPT_FILE = SKILL_CREATOR / "agents/grader.md"
AGGREGATE_SCRIPT = SKILL_CREATOR / "scripts/aggregate_benchmark.py"

EXECUTOR_TIMEOUT_S = 900
GRADER_TIMEOUT_S = 600
PRE_HOOK_TIMEOUT_S = 360

# Skills bundled into the claude binary that leak through every isolation. Set
# at runner startup via probe_builtin_skills() so an upgraded binary doesn't
# silently flag every run.
BUILTIN_SKILLS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Mode:
    skill: bool
    baseten_mcp: bool
    docs_mcp: bool

    @property
    def name(self) -> str:
        return f"s{int(self.skill)}b{int(self.baseten_mcp)}d{int(self.docs_mcp)}"

    @classmethod
    def parse(cls, s: str) -> Mode:
        if len(s) != 6 or s[0::2] != "sbd":
            raise ValueError(f"bad mode: {s} (expected s<0|1>b<0|1>d<0|1>)")
        return cls(skill=s[1] == "1", baseten_mcp=s[3] == "1", docs_mcp=s[5] == "1")

    @classmethod
    def cartesian(cls) -> list[Mode]:
        return [cls(*bs) for bs in itertools.product([True, False], repeat=3)]


EVALS_VENV_BIN = EVAL_ROOT / "harness" / ".venv" / "bin"

# Strict allowlist of env vars passed to claude subprocesses. Anything else
# (user's personal BASETEN_API_KEY from .zshrc, TRUSS_API_KEY, AWS keys, etc.)
# stays in the parent process and CANNOT leak into eval-driven tool calls.
# Earlier sweeps without this fix had agents shelling `truss push` with the
# user's personal key, deploying eval fixtures into the wrong workspace.
_ENV_ALLOWLIST = frozenset({
    "PATH",  # overridden below to inject evals/.venv/bin
    "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ",
    "USER", "LOGNAME",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL",
    # Baseten credentials are injected explicitly from BASETEN_MCP_KEY below,
    # so an unrelated BASETEN_API_KEY in the parent shell cannot override them.
})


def _subproc_env(work_root: Path) -> dict[str, str]:
    fake_home = work_root / "_home"
    fake_home.mkdir(parents=True, exist_ok=True)
    fake_home.chmod(0o700)
    # Scoped trussrc — single remote pointing at the test workspace. Agent's
    # `truss push` reads this; no env-var fallback, no other workspaces.
    trussrc = fake_home / ".trussrc"
    if not trussrc.exists():
        trussrc.write_text(
            "[baseten]\n"
            "remote_provider = baseten\n"
            f"api_key = {os.environ['BASETEN_MCP_KEY']}\n"
            "remote_url = https://app.baseten.co\n"
        )
    trussrc.chmod(0o600)
    env = {k: v for k, v in os.environ.items() if k in _ENV_ALLOWLIST}
    env["HOME"] = str(fake_home)
    env["PATH"] = f"{EVALS_VENV_BIN}:{env.get('PATH', '/usr/bin')}"
    # Test-workspace API key, exposed under both common names so the agent
    # finds it regardless of which it looks for. NOT the personal key from
    # the parent shell — strictly the test workspace key.
    key = os.environ["BASETEN_MCP_KEY"]
    env["BASETEN_API_KEY"] = key
    env["BASETEN_MCP_KEY"] = key
    return env


def sanitize(text: str) -> str:
    for name in ("BASETEN_MCP_KEY", "BASETEN_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        value = os.environ.get(name)
        if value:
            text = text.replace(value, "[REDACTED]")
    return text


def require_auth() -> None:
    if not os.environ.get("BASETEN_MCP_KEY"):
        raise ValueError("missing env: BASETEN_MCP_KEY")
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise ValueError("missing env: ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN")


def skill_hash(skill_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file() and "evals" not in path.relative_to(skill_dir).parts:
            digest.update(str(path.relative_to(skill_dir)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def external_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_relative_to(REPO.resolve()):
        raise ValueError(f"raw artifacts must be outside the repository: {path}")
    return path


def reject_ambient_skill_ancestors(path: Path) -> None:
    """Project settings discover skills in ancestors, even with an isolated HOME."""
    for ancestor in (path.resolve(), *path.resolve().parents):
        for relative in (".claude/skills", ".agents/skills"):
            directory = ancestor / relative
            if directory.is_dir() and any(directory.iterdir()):
                raise ValueError(
                    f"artifact directory inherits ambient skills from {directory}; "
                    "choose an artifact root outside that ancestor (for example /tmp/baseten-skills-evals)"
                )


def result_success(event: dict | None) -> bool:
    return bool(event and event.get("type") == "result" and
                event.get("subtype") == "success" and event.get("is_error") is False)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO).decode().strip()


def write_mcp_config(target: Path, mode: Mode) -> Path:
    """Per-run MCP config — only the servers selected by mode."""
    servers: dict[str, dict] = {}
    if mode.baseten_mcp:
        key = os.environ["BASETEN_MCP_KEY"]
        servers["baseten"] = {
            "type": "http",
            "url": "https://api.baseten.co/mcp",
            "headers": {"Authorization": f"Bearer {key}"},
        }
    if mode.docs_mcp:
        servers["baseten_docs"] = {"type": "http", "url": "https://docs.baseten.co/mcp"}
    path = target / "mcp.json"
    path.write_text(json.dumps({"mcpServers": servers}))
    path.chmod(0o600)
    return path


def setup_workdir(base: Path, skill_dir: Path | None) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    outputs = base / "outputs"
    outputs.mkdir(exist_ok=True)  # exist_ok for --resume on partially-completed units
    if skill_dir is not None:
        # Expose the skill to the agent at .claude/skills/<name>/, but EXCLUDE
        # the evals/ subdir — it contains assertions, expected outputs, and the
        # FIXTURE_MODEL_ID mapping, all of which would leak the rubric to the
        # agent under test. Symlink each agent-visible child individually.
        exposed_root = base / ".claude" / "skills" / skill_dir.name
        exposed_root.mkdir(parents=True, exist_ok=True)
        for child in skill_dir.iterdir():
            if child.name == "evals":
                continue
            link = exposed_root / child.name
            if not link.exists():
                link.symlink_to(child)
    return outputs


def probe_builtin_skills(bench_dir: Path, model: str | None = None) -> frozenset[str]:
    """One-shot probe: launch claude in max-isolation to capture binary-bundled skills."""
    probe = bench_dir / "_probe"
    probe.mkdir(exist_ok=True)
    (probe / "_home").mkdir(exist_ok=True)
    (probe / "mcp.json").write_text(json.dumps({"mcpServers": {}}))
    env = _subproc_env(probe / "run")  # creates probe/run/_home for HOME
    (probe / "run").mkdir(exist_ok=True)
    res = subprocess.run(
        ["claude", "-p", "hi", "--output-format", "stream-json", "--verbose",
         "--strict-mcp-config", "--mcp-config", str(probe / "mcp.json"),
         "--setting-sources", ""] + (["--model", model] if model else []),
        cwd=str(probe / "run"), env=env, capture_output=True, text=True, timeout=60,
    )
    (probe / "stdout.jsonl").write_text(sanitize(res.stdout))
    (probe / "stderr.txt").write_text(sanitize(res.stderr))
    events = [json.loads(line) for line in res.stdout.splitlines() if line.strip()]
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    if res.returncode or init is None or not result_success(result):
        raise RuntimeError(f"provider/isolation probe failed; see {probe}")
    return frozenset(init.get("skills", []))


def check_isolation(init_event: dict, mode: Mode, skill_name: str) -> dict:
    """Assert exact match of loaded skills + mcps against mode expectations."""
    expected_mcp = set()
    if mode.baseten_mcp:
        expected_mcp.add("baseten")
    if mode.docs_mcp:
        expected_mcp.add("baseten_docs")
    actual_mcp = {s["name"] for s in init_event.get("mcp_servers", []) if s.get("status") == "connected"}

    expected_skills = set(BUILTIN_SKILLS) | ({skill_name} if mode.skill else set())
    actual_skills = set(init_event.get("skills", []))

    expected_plugins: set = set()
    actual_plugins = set(init_event.get("plugins", []))

    mcp_diff = {"unexpected": sorted(actual_mcp - expected_mcp), "missing": sorted(expected_mcp - actual_mcp)}
    skill_diff = {"unexpected": sorted(actual_skills - expected_skills), "missing": sorted(expected_skills - actual_skills)}
    plugin_diff = {"unexpected": sorted(actual_plugins - expected_plugins), "missing": sorted(expected_plugins - actual_plugins)}

    passed = not (mcp_diff["unexpected"] or mcp_diff["missing"]
                  or skill_diff["unexpected"] or skill_diff["missing"]
                  or plugin_diff["unexpected"])
    return {
        "passed": passed,
        "expected": {"mcp": sorted(expected_mcp), "skills": sorted(expected_skills), "plugins": sorted(expected_plugins)},
        "actual": {"mcp": sorted(actual_mcp), "skills": sorted(actual_skills), "plugins": sorted(actual_plugins)},
        "diff": {"mcp": mcp_diff, "skills": skill_diff, "plugins": plugin_diff},
    }


def run_executor(*, eval_item: dict, work_root: Path, mode: Mode, skill_dir: Path, model: str | None, preamble: str | None) -> dict:
    outputs_dir = setup_workdir(work_root, skill_dir if mode.skill else None)
    mcp_path = write_mcp_config(work_root, mode)

    cmd = [
        "claude",
        "-p", eval_item["prompt"],
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        # Bypass all permission prompts — agent must act, not ask. Blast radius
        # is bounded by the test-workspace key (BASETEN_MCP_KEY), not by
        # tool-level filtering (Bash can exfil via 1000 paths; can't lock that
        # down without a network namespace).
        "--permission-mode", "bypassPermissions",
        "--strict-mcp-config",
        "--mcp-config", str(mcp_path),
        # "project" picks up the .claude/skills/ symlink in work_root. No
        # settings.json or CLAUDE.md exists there, so nothing else leaks in.
        "--setting-sources", "project",
    ]
    if model:
        cmd += ["--model", model]
    if preamble:
        cmd += ["--append-system-prompt", preamble]

    env = _subproc_env(work_root)

    t0 = time.time()
    tool_calls: Counter[str] = Counter()
    errors = 0
    tokens_in = tokens_out = tokens_cache_create = tokens_cache_read = 0
    cost_usd = None
    transcript_chunks: list[str] = []
    isolation = {"passed": False, "error": "no init event observed"}
    result = None
    # communicate drains stdout and stderr concurrently, avoiding a full stderr
    # pipe deadlock, while retaining the wall-clock deadline.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=str(work_root), env=env)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=EXECUTOR_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        stdout, stderr = proc.communicate()
    finally:
        mcp_path.unlink(missing_ok=True)
    raw = sanitize(stdout.decode("utf-8", errors="replace"))
    (work_root / "events.jsonl").write_text(raw)
    (work_root / "stderr.txt").write_text(sanitize(stderr.decode("utf-8", errors="replace")))
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        if t == "system" and ev.get("subtype") == "init":
            isolation = check_isolation(ev, mode, skill_dir.name)
        elif t in ("assistant", "user"):
            for block in ev.get("message", {}).get("content", []):
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "tool_use":
                    tool_calls[block.get("name", "?")] += 1
                    transcript_chunks.append("Tool call: " + json.dumps(block))
                elif btype == "tool_result":
                    transcript_chunks.append("Tool result: " + json.dumps(block))
                elif btype == "text":
                    transcript_chunks.append(block.get("text", ""))
        elif t == "result":
            result = ev
            usage = ev.get("usage", {}) or {}
            tokens_in = usage.get("input_tokens", 0) or 0
            tokens_out = usage.get("output_tokens", 0) or 0
            tokens_cache_create = usage.get("cache_creation_input_tokens", 0) or 0
            tokens_cache_read = usage.get("cache_read_input_tokens", 0) or 0
            # Claude's price table cannot price third-party provider models.
            if os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/") == "https://api.anthropic.com":
                cost_usd = ev.get("total_cost_usd")
    executor_ok = not timed_out and proc.returncode == 0 and result_success(result)
    if not executor_ok:
        errors += 1

    duration = round(time.time() - t0, 2)
    if not isolation.get("passed"):
        errors += 1

    transcript_path = work_root / "transcript.md"
    transcript_path.write_text(
        f"# Executor transcript\n\nPrompt:\n\n{eval_item['prompt']}\n\n---\n\n"
        + "\n\n".join(transcript_chunks)
    )
    output_chars = sum(p.stat().st_size for p in outputs_dir.rglob("*") if p.is_file())

    (work_root / "isolation.json").write_text(json.dumps(isolation, indent=2))
    (work_root / "metrics.json").write_text(json.dumps({
        "tool_calls": dict(tool_calls),
        "total_tool_calls": sum(tool_calls.values()),
        "errors_encountered": errors,
        "output_chars": output_chars,
        "transcript_chars": transcript_path.stat().st_size,
        "isolation_passed": isolation.get("passed", False),
    }, indent=2))
    # Gross input tokens = the model's total "stuff to think about" across the
    # session, ignoring caching (uncached + cache_create + cache_read). Useful as
    # a caching-agnostic complexity measure that doesn't vary with cache TTL or
    # provider pricing changes. Cost is unavailable for custom providers.
    gross_input_tokens = tokens_in + tokens_cache_create + tokens_cache_read
    (work_root / "timing.json").write_text(json.dumps({
        "executor_duration_seconds": duration,
        "total_duration_seconds": duration,
        "cost_usd": round(cost_usd, 6) if cost_usd is not None else None,
        "gross_input_tokens": gross_input_tokens,
        "output_tokens": tokens_out,
        "tokens_in_uncached": tokens_in,
        "tokens_cache_create": tokens_cache_create,
        "tokens_cache_read": tokens_cache_read,
    }, indent=2))
    status = {"duration": duration, "isolation_passed": isolation.get("passed", False),
              "executor_ok": executor_ok, "returncode": proc.returncode, "timed_out": timed_out}
    (work_root / "executor_status.json").write_text(json.dumps(status, indent=2))
    return status


def run_grader(*, eval_item: dict, work_root: Path, model: str | None) -> None:
    expectations = [a["text"] for a in eval_item["assertions"]]
    grader_md = GRADER_PROMPT_FILE.read_text()
    prompt = (
        grader_md
        + "\n\n---\n\n## Run Inputs\n\n"
        + f"- expectations: {json.dumps(expectations)}\n"
        + f"- transcript_path: {work_root / 'transcript.md'}\n"
        + f"- outputs_dir: {work_root / 'outputs'}\n\n"
        + "Write the grading JSON to "
        + str(work_root / "grading.json")
        + " (use that exact absolute path)."
        + " Copy every expectation text verbatim, including punctuation and capitalization, in the supplied order."
        + " Read metrics.json and timing.json from "
        + str(work_root)
        + " for the execution_metrics and timing fields."
    )
    cmd = ["claude", "-p", prompt, "--permission-mode", "bypassPermissions", "--output-format", "json",
           "--strict-mcp-config", "--setting-sources", ""]
    if model:
        cmd += ["--model", model]
    env = _subproc_env(work_root)
    try:
        res = subprocess.run(cmd, cwd=str(work_root), env=env, timeout=GRADER_TIMEOUT_S,
                             capture_output=True, text=True, check=False)
    except subprocess.TimeoutExpired as exc:
        for filename, output in (("grader_stdout.json", exc.stdout), ("grader_stderr.txt", exc.stderr)):
            text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else (output or "")
            (work_root / filename).write_text(sanitize(text))
        raise RuntimeError("grader timed out; partial output saved") from exc
    (work_root / "grader_stdout.json").write_text(sanitize(res.stdout))
    (work_root / "grader_stderr.txt").write_text(sanitize(res.stderr))
    try:
        result = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("grader returned invalid structured output") from exc
    if res.returncode or not result_success(result):
        raise RuntimeError("grader provider/execution failed; see grader_stdout.json")
    grading_file = work_root / "grading.json"
    if not grading_file.exists():
        raise RuntimeError("grader produced no grading.json")
    grading_file.write_text(sanitize(grading_file.read_text()))
    validate_grading(json.loads(grading_file.read_text()), expectations)


def validate_grading(grading: dict, expectations: list[str]) -> None:
    grades = grading.get("expectations", [])
    if len(grades) != len(expectations) or any(
        g.get("text") != expected or type(g.get("passed")) is not bool or not isinstance(g.get("evidence"), str)
        for g, expected in zip(grades, expectations)
    ):
        raise ValueError("grader assertions are missing, reordered, or malformed")
    passed = sum(g["passed"] for g in grades)
    expected_summary = {"passed": passed, "failed": len(grades) - passed,
                        "total": len(grades), "pass_rate": passed / len(grades) if grades else 0.0}
    summary = grading.get("summary", {})
    for key, value in expected_summary.items():
        if not isinstance(summary.get(key), (int, float)) or abs(summary[key] - value) > (0.0051 if key == "pass_rate" else 0):
            raise ValueError(f"inconsistent grading summary: {key}")


_STATS_LOCK = threading.Lock()
_PRINT_LOCK = threading.Lock()
_FIXTURE_LOCKS: dict[str, threading.Lock] = {}
_FIXTURE_LOCKS_GUARD = threading.Lock()


def _fixture_lock(name: str) -> threading.Lock:
    """Per-fixture lock so concurrent runs against the same mutating fixture serialize."""
    with _FIXTURE_LOCKS_GUARD:
        if name not in _FIXTURE_LOCKS:
            _FIXTURE_LOCKS[name] = threading.Lock()
        return _FIXTURE_LOCKS[name]


def fixture_lock_key(fixture: str, model_id: str | None) -> str:
    # Partition by credential/workspace and actual remote model, not arm or eval.
    identity = os.environ["BASETEN_MCP_KEY"] + "\0" + (model_id or fixture)
    return hashlib.sha256(identity.encode()).hexdigest()


@contextlib.contextmanager
def fixture_execution_lock(fixture: str | None, model_id: str | None):
    """Serialize fixture reset and execution across concurrent benchmark arms."""
    if not fixture:
        yield
        return
    key = fixture_lock_key(fixture, model_id)
    lock_root = Path(tempfile.gettempdir()) / "baseten-skills-evals-locks"
    lock_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_root.chmod(0o700)
    # Keep the in-process lock as well: flock semantics differ between OSes.
    with _fixture_lock(key):
        fd = os.open(lock_root / f"{key}.lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _run_pre_hook(fixture: str | None, fixture_model_id: str | None, fixture_model_name: str | None = None,
                  work_root: Path | None = None) -> None:
    """Run harness/fixtures/<name>/pre_run.sh if present. Inherits parent env + adds FIXTURE_MODEL_ID."""
    if not fixture:
        return
    script = EVAL_ROOT / "harness" / "fixtures" / fixture / "pre_run.sh"
    if not script.exists():
        return
    env = dict(os.environ)
    if fixture_model_id:
        env["FIXTURE_MODEL_ID"] = fixture_model_id
    if fixture_model_name:
        env["FIXTURE_MODEL_NAME"] = fixture_model_name
    try:
        res = subprocess.run([str(script)], env=env, check=False, timeout=PRE_HOOK_TIMEOUT_S,
                             capture_output=True, text=True)
    except subprocess.TimeoutExpired as exc:
        if work_root:
            for filename, output in (("pre_hook_stdout.txt", exc.stdout), ("pre_hook_stderr.txt", exc.stderr)):
                text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else (output or "")
                (work_root / filename).write_text(sanitize(text))
        raise RuntimeError("fixture pre-hook timed out; see pre_hook logs") from exc
    if work_root:
        (work_root / "pre_hook_stdout.txt").write_text(sanitize(res.stdout))
        (work_root / "pre_hook_stderr.txt").write_text(sanitize(res.stderr))
    if res.returncode:
        raise RuntimeError(f"fixture pre-hook failed with exit code {res.returncode}; see pre_hook logs")


def _log(msg: str) -> None:
    with _PRINT_LOCK:
        print(msg, flush=True)


ASSERTION_WEIGHTS = {"core": 1.0, "nice": 0.25}


def _weighted_score(grading: dict, eval_item: dict) -> tuple[float, float, float]:
    """Return (weighted_passed, weighted_total, weighted_pass_rate). Falls back to unweighted if grading shape is unexpected."""
    expectations = grading.get("expectations") or []
    assertions = eval_item.get("assertions") or []
    if len(expectations) != len(assertions):
        s = grading.get("summary", {})
        return float(s.get("passed", 0)), float(s.get("total", 0)), float(s.get("pass_rate", 0.0))
    wp = wt = 0.0
    for grade, spec in zip(expectations, assertions):
        w = ASSERTION_WEIGHTS.get(spec.get("weight", "core"), 1.0)
        wt += w
        if grade.get("passed"):
            wp += w
    return wp, wt, (wp / wt if wt else 0.0)


def append_stats_row(stats_path: Path, *, ts: str, sha: str, model: str, eval_item: dict,
                     mode: Mode, run_idx: int, work_root: Path, provenance: dict | None = None) -> None:
    grading = json.loads((work_root / "grading.json").read_text())
    timing = json.loads((work_root / "timing.json").read_text())
    metrics = json.loads((work_root / "metrics.json").read_text())
    summary = grading.get("summary", {})
    wp, wt, wpr = _weighted_score(grading, eval_item)
    wall_s = timing.get("total_duration_seconds", 0.0)
    cost_usd = timing.get("cost_usd", 0.0)
    gross_input_tokens = timing.get("gross_input_tokens", 0)
    output_tokens = timing.get("output_tokens", 0)
    # Detect grader-no-output placeholder rows so the aggregator can drop them
    # rather than treat as 0 (which corrupts marginals).
    grader_failed = any(
        "grader produced no output" in (e.get("evidence") or "")
        for e in grading.get("expectations", [])
    )
    row = {
        "ts": ts, "sha": sha, "model": model,
        **(provenance or {}),
        "eval_id": eval_item["id"], "mode": mode.name, "run": run_idx,
        "complexity": eval_item.get("complexity", 1),
        "skill": mode.skill, "baseten_mcp": mode.baseten_mcp, "docs_mcp": mode.docs_mcp,
        "passed": None if grader_failed else summary.get("passed", 0),
        "total": summary.get("total", 0),
        "pass_rate": None if grader_failed else summary.get("pass_rate", 0.0),
        "weighted_passed": None if grader_failed else round(wp, 4),
        "weighted_total": round(wt, 4),
        "weighted_pass_rate": None if grader_failed else round(wpr, 4),
        "grader_status": "no_output" if grader_failed else "ok",
        "wall_s": wall_s,
        "cost_usd": cost_usd,
        "gross_input_tokens": gross_input_tokens,
        "output_tokens": output_tokens,
        "tool_calls": metrics.get("total_tool_calls", 0),
        "errors": metrics.get("errors_encountered", 0),
        "isolation_passed": metrics.get("isolation_passed", False),
    }
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with _STATS_LOCK, stats_path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def parse_modes(spec: str) -> list[Mode]:
    if spec == "all":
        return Mode.cartesian()
    return [Mode.parse(s.strip()) for s in spec.split(",") if s.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True, help="Skill name under skills/")
    ap.add_argument("--modes", default="s1b1d1",
                    help='Comma-separated mode names (e.g. "s1b1d1,s0b0d0") or "all" for cartesian. '
                         'Each is s<0|1>b<0|1>d<0|1>: skill, baseten MCP, docs MCP.')
    ap.add_argument("--ids", type=int, nargs="*", help="Eval IDs to run (default: all)")
    ap.add_argument("--runs", type=int, default=5, help="Repetitions per (eval × mode). Default 5 — at N=3, Wilson 95%% CI on binary pass is ~±0.5; N≥5 gets useful.")
    ap.add_argument("--model", default=None, help="Provider model id (default: ANTHROPIC_MODEL or CLI default)")
    ap.add_argument("--skill-source", type=Path, help="Skill directory to expose; eval definitions always come from this checkout")
    ap.add_argument("--fixtures-path", type=Path, help="Fixture mapping override")
    ap.add_argument("--artifact-root", type=Path, default=Path(tempfile.gettempdir()) / "baseten-skills-evals",
                    help="Persistent raw artifact directory outside the repository")
    ap.add_argument("--out", default="runs", help="Symlink dir for artifacts (default: runs/, gitignored)")
    ap.add_argument("--num-workers", type=int, default=1, help="Max parallel (eval × mode × run) workers (default 1 — higher values trigger throttling on the single-workspace test account)")
    ap.add_argument("--stats-path", default=None, help="Override stats.jsonl path (default: results/stats.jsonl)")
    ap.add_argument("--resume", default=None, help="Resume an interrupted sweep — point at its /tmp bench_dir; successfully completed units are skipped.")
    args = ap.parse_args()

    load_dotenv(EVAL_ROOT / ".env", override=False)
    try:
        require_auth()
        artifact_root = external_path(args.artifact_root)
        reject_ambient_skill_ancestors(artifact_root)
        if args.resume:
            reject_ambient_skill_ancestors(external_path(Path(args.resume)))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    args.model = args.model or os.environ.get("ANTHROPIC_MODEL")
    modes = parse_modes(args.modes)
    current_skill_dir = REPO / "skills" / args.skill
    skill_dir = (args.skill_source or current_skill_dir).resolve()
    if not (skill_dir / "SKILL.md").is_file():
        ap.error(f"skill source has no SKILL.md: {skill_dir}")
    evals_path = current_skill_dir / "evals/evals.json"
    evals_data = json.loads(evals_path.read_text())
    preamble = evals_data.get("preamble")
    eval_set = evals_data["evals"]
    if args.ids:
        eval_set = [e for e in eval_set if e["id"] in set(args.ids)]

    fixtures_path = args.fixtures_path or current_skill_dir / "evals/fixtures.json"
    fixtures: dict[str, dict[str, str]] = json.loads(fixtures_path.read_text()) if fixtures_path.exists() else {}

    def resolve(item: dict) -> dict | None:
        """Substitute fixture placeholders. Returns None if a required fixture is missing."""
        fname = item.get("fixture")
        if not fname:
            return item
        if fname not in fixtures:
            _log(f"[skip] eval={item['id']} {item['name']}: fixture {fname!r} not in {fixtures_path}")
            return None
        out = dict(item)
        for k, v in fixtures[fname].items():
            # Underscore-prefixed keys are metadata (e.g. _serialize), not placeholders.
            if k.startswith("_") or not isinstance(v, str):
                continue
            ph = "{{" + k + "}}"
            out["prompt"] = out["prompt"].replace(ph, v)
            out["assertions"] = [{**a, "text": a["text"].replace(ph, v)} for a in out["assertions"]]
        # Stash for the worker — pre-run hook + per-fixture lock need these.
        out["_fixture_model_id"] = fixtures[fname].get("FIXTURE_MODEL_ID")
        out["_fixture_model_name"] = fixtures[fname].get("FIXTURE_MODEL_NAME")
        return out

    eval_set = [r for r in (resolve(e) for e in eval_set) if r is not None]
    if not eval_set:
        print("No evals matched (after fixture resolution)", file=sys.stderr)
        return 1
    if not GRADER_PROMPT_FILE.exists():
        print("third_party/skill-creator missing — run evals/baseten/bin/fetch_skill_creator.sh", file=sys.stderr)
        return 1

    if args.resume:
        bench_dir = Path(args.resume).resolve()
        if not bench_dir.exists():
            print(f"resume dir does not exist: {bench_dir}", file=sys.stderr)
            return 1
        # Recover ts + sha from bench_dir name: baseten-skills-evals_<ts>_<sha>_<rand>
        parts = bench_dir.name.split("_")
        ts, sha = parts[1], parts[2]
        _log(f"resuming bench_dir={bench_dir} ts={ts} sha={sha}")
    else:
        ts = utcnow()
        sha = git_sha()
        # Persistent artifact root — survives /tmp purges.
        runs_root = artifact_root
        runs_root.mkdir(parents=True, exist_ok=True)
        bench_dir = runs_root / f"baseten-skills-evals_{ts}_{sha}"
        bench_dir.mkdir()
        link_root = EVAL_ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        link_root.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(FileExistsError):
            (link_root / f"{ts}__{sha}").symlink_to(bench_dir)
    stats_path = external_path(Path(args.stats_path)) if args.stats_path else bench_dir / "stats.jsonl"
    provenance = {"provider": os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
                  "skill_source": str(skill_dir), "skill_sha256": skill_hash(skill_dir),
                  "evals_sha256": hashlib.sha256(evals_path.read_bytes()).hexdigest(),
                  "fixtures_sha256": hashlib.sha256(fixtures_path.read_bytes()).hexdigest() if fixtures_path.exists() else None}
    provenance_file = bench_dir / "provenance.json"
    run_provenance = {**provenance, "model": args.model, "modes": [m.name for m in modes]}
    if args.resume and provenance_file.exists() and json.loads(provenance_file.read_text()) != run_provenance:
        raise ValueError("resume provenance differs from the original run")
    provenance_file.write_text(json.dumps(run_provenance, indent=2))

    global BUILTIN_SKILLS
    BUILTIN_SKILLS = probe_builtin_skills(bench_dir, args.model)
    _log(f"builtin_skills (from probe): {sorted(BUILTIN_SKILLS)}")
    _log(f"modes={[m.name for m in modes]} evals={[e['id'] for e in eval_set]} runs={args.runs} num_workers={args.num_workers}")

    # Pre-create eval roots + metadata so workers only touch their own subdir.
    # On --resume, skip units with a successful completion marker.
    #
    # Fixture locks serialize reset and execution across workers and processes.
    for item in eval_set:
        eid = item["id"]
        eval_root = bench_dir / f"eval-{eid:03d}"
        eval_root.mkdir(exist_ok=True)
        (eval_root / "eval_metadata.json").write_text(sanitize(json.dumps({**{k: v for k, v in item.items() if not k.startswith("_")},
                                                                        "eval_id": eid, "preamble": preamble}, indent=2)))
    work_units: list[tuple[dict, Mode, int, Path]] = []
    skipped = 0
    for run_idx in range(1, args.runs + 1):
        for mode in modes:
            for item in eval_set:
                eid = item["id"]
                work_root = bench_dir / f"eval-{eid:03d}" / mode.name / f"run-{run_idx}"
                if (work_root / "completed.json").exists():
                    skipped += 1
                    continue
                work_root.mkdir(parents=True, exist_ok=True)
                work_units.append((item, mode, run_idx, work_root))
    if skipped:
        _log(f"resume: skipping {skipped} successfully completed units")

    failures: list[dict] = []

    def _do_unit(unit: tuple[dict, Mode, int, Path]) -> None:
        item, mode, run_idx, work_root = unit
        eid = item["id"]
        fixture = item.get("fixture")
        _log(f"[start] eval={eid} mode={mode.name} run={run_idx}")
        try:
            # Hold through execution so another arm cannot reset a live fixture
            # while this executor observes or mutates it. Grading needs no lock.
            with fixture_execution_lock(fixture, item.get("_fixture_model_id")):
                _run_pre_hook(fixture, item.get("_fixture_model_id"), item.get("_fixture_model_name"), work_root)
                r = run_executor(eval_item=item, work_root=work_root, mode=mode,
                                 skill_dir=skill_dir, model=args.model, preamble=preamble)
            if not r["executor_ok"] or not r["isolation_passed"]:
                raise RuntimeError("executor or isolation failed; quality grading skipped")
            run_grader(eval_item=item, work_root=work_root, model=args.model)
            append_stats_row(stats_path, ts=ts, sha=sha, model=args.model or "default",
                             eval_item=item, mode=mode, run_idx=run_idx, work_root=work_root, provenance=provenance)
            (work_root / "completed.json").write_text(json.dumps({"status": "ok"}))
            _log(f"[done]  eval={eid} mode={mode.name} run={run_idx}")
        except Exception as exc:
            failure = {"eval_id": eid, "mode": mode.name, "run": run_idx, "error": sanitize(repr(exc))}
            (work_root / "failure.json").write_text(json.dumps(failure, indent=2))
            with _STATS_LOCK:
                failures.append(failure)
            _log(f"[fail] eval={eid} mode={mode.name} run={run_idx}: {failure['error']}")

    # Work-stealing scheduler: workers pull from a deque. Units gated by an
    # in-use fixture (_serialize=True) get requeued instead of blocking.
    from collections import deque  # noqa: PLC0415
    queue: deque = deque(work_units)
    queue_lock = threading.Lock()
    in_use_fixtures: set[str] = set()

    def _worker() -> None:
        while True:
            with queue_lock:
                # Find first unit whose fixture is not currently in-use.
                picked = None
                for _ in range(len(queue)):
                    unit = queue.popleft()
                    fname = unit[0].get("fixture")
                    serialize = fname and fixtures.get(fname, {}).get("_serialize") is True
                    if serialize and fname in in_use_fixtures:
                        queue.append(unit)  # not ready — requeue
                        continue
                    if serialize:
                        in_use_fixtures.add(fname)
                    picked = (unit, fname if serialize else None)
                    break
                if picked is None:
                    if not queue:
                        return
                    # All remaining units are blocked on locks held elsewhere; brief wait.
                    pass
            if picked is None:
                time.sleep(1)
                continue
            unit, claimed = picked
            try:
                _do_unit(unit)
            finally:
                if claimed:
                    with queue_lock:
                        in_use_fixtures.discard(claimed)

    with ThreadPoolExecutor(max_workers=args.num_workers) as ex:
        futures = [ex.submit(_worker) for _ in range(args.num_workers)]
        for future in futures:
            future.result()

    (bench_dir / "failures.json").write_text(json.dumps(failures, indent=2))
    if failures:
        print(f"{len(failures)} units failed; no quality aggregate produced. Artifacts: {bench_dir}")
        return 1
    subprocess.run([sys.executable, str(AGGREGATE_SCRIPT), str(bench_dir)],
                   cwd=str(SKILL_CREATOR), check=True)
    print(f"Done. Artifacts: {bench_dir}")
    print(f"Stats: {stats_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
