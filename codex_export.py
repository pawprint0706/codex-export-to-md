#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex CLI 세션 기록을 프로젝트 폴더별 Markdown으로 내보내는 도구.

Codex CLI는 세션 기록을 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`에 저장한다.
Orca 앱은 자체 codex-home을 따로 관리한다(.codex-open-design, Orca runtime/account home 등).
이 스크립트는 표준 경로와 Orca 경로를 모두 탐색하여 동일 세션은 중복 제거하고,
작업 폴더(cwd)별로 묶어 대화를 읽기 좋은 Markdown으로 변환해 내보낸다.

함께 생성되는 `viewer.html`은 웹 뷰어로, 내보낸 `projects` 폴더 아래의
md 파일을 실행 시점에 직접 읽어(폴더 선택) 파싱하여 표시한다.
`projects/README.md`는 사이드바 최상단의 '개요' 메뉴로 보여준다.

사용법:
    python codex_export.py
    python codex_export.py --sessions-dir "C:\\Users\\me\\.codex\\sessions" -o export
    python codex_export.py --include-tool-output

옵션:
    --sessions-dir DIR       세션 JSONL 폴더 (여러 번 지정 가능)
                             미지정 시 표준(~/.codex) + Orca 경로 자동 탐색
    -o, --output DIR         내보낼 폴더 (기본: ./codex_export)
    --include-tool-output    도구 호출(쉘 명령 등)의 실행 출력도 포함
    --no-viewer              웹 뷰어 생성 생략
"""

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_SESSIONS_DIR = Path.home() / ".codex" / "sessions"
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
ENV_CTX_RE = re.compile(r"<environment_context>.*?</environment_context>", re.S)
DATA_IMG_RE = re.compile(r"data:image/(png|jpe?g|gif|webp);base64,(.+)", re.S)
INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*]')
MAX_OUTPUT_CHARS = 30000


def parse_dt(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def to_local(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone()


def fmt_time(dt):
    dt = to_local(dt)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def fmt_time_long(dt):
    dt = to_local(dt)
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M %Z")


def content_text(content):
    parts = []
    for item in content or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") in ("text", "input_text", "output_text"):
            txt = item.get("text") or ""
            if txt:
                parts.append(txt)
    return "\n".join(parts)


def collect_images(content):
    images = []
    for item in content or []:
        if not isinstance(item, dict) or item.get("type") != "input_image":
            continue
        url = item.get("image_url")
        if isinstance(url, dict):
            url = url.get("url", "")
        if isinstance(url, str) and url.startswith("data:image"):
            m = DATA_IMG_RE.match(url)
            if m:
                ext = "jpg" if m.group(1) == "jpeg" else m.group(1)
                try:
                    images.append((base64.b64decode(m.group(2)), ext))
                except Exception:
                    continue
    return images


def strip_env_context(text):
    stripped = ENV_CTX_RE.sub("", text).strip()
    return stripped


def fence(text, lang="text"):
    if not text:
        return ""
    runs = re.findall(r"`+", text)
    depth = max((len(r) for r in runs), default=0)
    ticks = "`" * max(3, depth + 1)
    return f"{ticks}{lang}\n{text}\n{ticks}"


def tool_command_text(payload):
    ptype = payload.get("type")
    if ptype == "function_call":
        raw = payload.get("arguments") or ""
        if isinstance(raw, str):
            try:
                args = json.loads(raw)
            except json.JSONDecodeError:
                return raw.strip(), ""
            if isinstance(args, dict):
                cmd = args.get("command") or args.get("cmd") or args.get("script") or ""
                return str(cmd), str(args.get("workdir") or "")
            return json.dumps(args, ensure_ascii=False, indent=2), ""
        return json.dumps(raw, ensure_ascii=False, indent=2), ""
    raw = payload.get("input") or ""
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False, indent=2), ""
    return str(raw), ""


def load_session(path):
    meta = {}
    events = []
    outputs = {}
    seen_ids = set()
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return None

    def append_message(role, text, images, msg_id, dt, phase=None):
        if not text.strip():
            return False
        if msg_id and msg_id in seen_ids:
            return False
        if msg_id:
            seen_ids.add(msg_id)
        if role == "user":
            if not strip_env_context(text):
                return False
            events.append({"kind": "user", "dt": dt, "text": text, "images": images})
        elif role == "assistant":
            kind = "assistant" if (phase == "final_answer" or not phase) else "commentary"
            events.append({"kind": kind, "dt": dt, "text": text})
        return True

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        rtype = rec.get("type")
        payload = rec.get("payload") or {}
        dt = parse_dt(rec.get("timestamp"))

        if rtype == "session_meta":
            meta.update(payload)
            if not meta.get("timestamp") and dt:
                meta["timestamp"] = dt
            continue
        if rtype == "turn_context":
            meta.setdefault("cwd", payload.get("cwd"))
            meta.setdefault("model", payload.get("model"))
            continue
        if rtype == "compacted":
            if events and events[-1]["kind"] != "compaction":
                events.append({"kind": "compaction", "dt": dt})
            for msg in payload.get("replacement_history") or []:
                if not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant"):
                    continue
                append_message(
                    msg.get("role"),
                    content_text(msg.get("content")),
                    collect_images(msg.get("content")),
                    msg.get("id"),
                    None,
                )
            continue
        if rtype != "response_item":
            continue
        ptype = payload.get("type")
        if ptype == "message":
            append_message(
                payload.get("role"),
                content_text(payload.get("content")),
                collect_images(payload.get("content")),
                payload.get("id"),
                dt,
                payload.get("phase"),
            )
        elif ptype in ("function_call", "custom_tool_call"):
            cmd, workdir = tool_command_text(payload)
            events.append({
                "kind": "tool",
                "dt": dt,
                "name": payload.get("name") or ptype,
                "command": cmd,
                "workdir": workdir,
                "call_id": payload.get("call_id") or payload.get("id"),
            })
        elif ptype in ("function_call_output", "custom_tool_call_output"):
            call_id = payload.get("call_id") or payload.get("id")
            if call_id:
                out = payload.get("output")
                if isinstance(out, dict):
                    out = json.dumps(out, ensure_ascii=False, indent=2)
                outputs[call_id] = str(out or "")
    return {"meta": meta, "events": events, "outputs": outputs}


def discover_session_dirs():
    dirs = []
    if DEFAULT_SESSIONS_DIR.is_dir():
        dirs.append(DEFAULT_SESSIONS_DIR)
    for home in Path.home().glob(".codex-*/sessions"):
        if home.is_dir() and home not in dirs:
            dirs.append(home)
    roaming = Path(os.environ.get("APPDATA") or "") / "Orca"
    rt = roaming / "codex-runtime-home" / "home" / "sessions"
    if rt.is_dir():
        dirs.append(rt)
    for acc in (roaming / "codex-accounts").glob("*/home/sessions"):
        if acc.is_dir():
            dirs.append(acc)
    return dirs


def source_label(root):
    root = Path(root).resolve()
    if os.path.normcase(str(root)) == os.path.normcase(str(DEFAULT_SESSIONS_DIR.resolve())):
        return "표준 ~/.codex"
    s = root.as_posix()
    if "codex-runtime-home" in s:
        return "Orca runtime home"
    if "/codex-accounts/" in s:
        return "Orca 계정 홈"
    m = re.search(r"/\.codex([^/]*)", s)
    if m:
        return f"~/.codex{m.group(1)}"
    return str(root)


def load_all_sessions(session_dirs):
    sessions = []
    best = {}
    for root in session_dirs:
        label = source_label(root)
        for f in sorted(root.rglob("rollout-*.jsonl")):
            loaded = load_session(f)
            if loaded is None:
                continue
            loaded["path"] = f
            loaded["source"] = label
            sid = loaded["meta"].get("session_id")
            size = f.stat().st_size
            if sid:
                prev = best.get(sid)
                if prev is not None:
                    if size > prev["size"]:
                        best[sid] = {**loaded, "size": size}
                    continue
                best[sid] = {**loaded, "size": size}
            else:
                sessions.append(loaded)
    sessions.extend(best.values())
    return sessions


def title_for(events):
    for ev in events:
        if ev["kind"] == "user":
            t = re.sub(r"[#*`_>\[\]|~-]", " ", ev["text"])
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) > 60:
                t = t[:60].rstrip() + "..."
            return t or "제목 없음"
    return "제목 없음"


def sanitize_name(name, max_len=60):
    name = INVALID_FS_CHARS.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip().strip(" .")
    if len(name) > max_len:
        name = name[:max_len].strip(" ._")
    return name or "untitled"


def assign_folder_names(keys):
    used = {}
    result = {}
    for key in keys:
        parts = [p for p in key.split(os.sep) if p] if key else []
        if not parts:
            result[key] = "_기타"
            continue
        cand = parts[-1]
        i = len(parts) - 2
        while cand.lower() in used and used[cand.lower()] != key:
            if i >= 0:
                cand = "_".join(parts[i:])
                i -= 1
            else:
                cand = cand + "_"
        used[cand.lower()] = key
        result[key] = sanitize_name(cand)
    return result


def session_start(sess):
    return to_local(parse_dt(sess["meta"].get("timestamp")) or None)


def build_meta_rows(meta, start):
    rows = [("시작", fmt_time_long(start))]
    if meta.get("cwd"):
        rows.append(("프로젝트", f"`{meta['cwd']}`"))
    git = meta.get("git") or {}
    if git.get("branch"):
        git_text = f"`{git['branch']} @ {str(git.get('commit_hash'))[:8]}`"
        repo = str(git.get("repository_url") or "")
        if repo:
            repo = repo[:-4] if repo.endswith(".git") else repo
            repo_name = repo.rstrip("/").split("/")[-1] or "저장소"
            git_text += f" · [{repo_name}]({repo})"
        rows.append(("Git", git_text))
    model = meta.get("model") or meta.get("model_provider")
    if model:
        rows.append(("모델", str(model)))
    if meta.get("cli_version"):
        rows.append(("CLI 버전", str(meta["cli_version"])))
    if meta.get("session_id"):
        rows.append(("세션 ID", f"`{meta['session_id']}`"))
    return rows


def render_session_markdown(sess, src_rel, include_tool_output):
    meta, events, outputs = sess["meta"], sess["events"], sess["outputs"]
    title = title_for(events)
    start = session_start(sess)
    asset_names = sess.get("asset_names") or []
    asset_index = 0
    out = []
    out.append(f"# {title}")
    out.append("")
    source = sess.get("source") or ""
    out.append(f"> 출처: `{src_rel}` · {source}")
    out.append("")
    rows = build_meta_rows(meta, start)
    out.append("| 항목 | 값 |")
    out.append("|---|---|")
    for k, v in rows:
        v = v.replace("|", "\\|").replace("\n", " ")
        out.append(f"| {k} | {v} |")
    out.append("")
    out.append("---")
    out.append("")

    for ev in events:
        kind = ev["kind"]
        stamp = fmt_time(ev.get("dt"))
        label = lambda s: f"{s}{' · ' + stamp if stamp else ''}"
        if kind == "user":
            out.append(f"#### {label('🧑 사용자')}")
            out.append("")
            out.append(ev["text"].strip())
            out.append("")
            for i, (data, ext) in enumerate(ev.get("images") or [], 1):
                name = asset_names[asset_index] if asset_index < len(asset_names) else ""
                asset_index += 1
                if name:
                    out.append(f"![첨부 이미지 {i}](assets/{name})")
            if ev.get("images"):
                out.append("")
        elif kind == "assistant":
            out.append(f"#### {label('🤖 Codex')}")
            out.append("")
            out.append(ev["text"].strip())
            out.append("")
        elif kind == "commentary":
            text = ev["text"].strip().replace("\n", "\n> ")
            out.append(f"> 💬 **진행 메모**{(' · ' + stamp) if stamp else ''}")
            out.append(">")
            out.append(f"> {text}")
            out.append("")
        elif kind == "tool":
            summary = f"🛠️ {ev['name']}"
            if ev.get("workdir"):
                summary += f" · `{ev['workdir']}`"
            out.append("<details>")
            out.append(f"<summary>{summary}</summary>")
            out.append("")
            if ev.get("command"):
                out.append(fence(ev["command"]))
                out.append("")
            if include_tool_output:
                raw = outputs.get(ev.get("call_id")) if ev.get("call_id") else None
                if raw:
                    cleaned = ANSI_RE.sub("", raw).strip()
                    if len(cleaned) > MAX_OUTPUT_CHARS:
                        cleaned = cleaned[:MAX_OUTPUT_CHARS] + "\n...(출력 생략)"
                    out.append("**출력:**")
                    out.append("")
                    out.append(fence(cleaned))
                    out.append("")
            out.append("</details>")
            out.append("")
        elif kind == "compaction":
            out.append("> ⚠️ 대화가 압축되어 요약되었습니다. 아래 메시지들은 압축 전 기록에서 복원되었습니다.")
            out.append("")

    if not events:
        out.append("이 세션에는 기록된 대화가 없습니다.")
    return "\n".join(out)


def collect_assets(events):
    assets = []
    for ev in events:
        if ev["kind"] == "user":
            for data, ext in ev.get("images") or []:
                assets.append((data, ext))
    return assets


def build_project_readme(folder_name, cwd, sessions):
    out = []
    out.append(f"# {folder_name}")
    out.append("")
    out.append(f"> 프로젝트: `{cwd or '(알 수 없음)'}` · 세션 {len(sessions)}개")
    out.append("")
    out.append("| 날짜 | 제목 |")
    out.append("|---|---|")
    for i, sess in enumerate(sessions, 1):
        start = session_start(sess)
        stamp = start.strftime("%Y-%m-%d %H:%M") if start else "-"
        title = title_for(sess["events"])
        out.append(f"| {stamp} | [{title}](./{sess['filename']}) |")
    out.append("")
    return "\n".join(out)


def build_top_readme(projects, sessions, session_dirs, include_tool_output):
    out = []
    out.append("# Codex 세션 기록")
    out.append("")
    out.append(f"- 내보낸 시점: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}")
    out.append(f"- 고유 세션: {len(sessions)}개 · 프로젝트: {len(projects)}개")
    src_counts = {}
    for s in sessions:
        src_counts[s.get("source") or "(알 수 없음)"] = src_counts.get(s.get("source") or "(알 수 없음)", 0) + 1
    src_txt = ", ".join(f"{k} {v}개" for k, v in sorted(src_counts.items()))
    out.append(f"- 선택된 소스: {src_txt}")
    out.append("- 탐색 대상:")
    for d in session_dirs:
        if d.exists():
            out.append(f"  - `{d}`")
    if include_tool_output:
        out.append("- 도구 실행 출력 포함: 예")
    out.append("- 웹 뷰어: `../viewer.html` — 열고 '폴더 열기'로 `projects` 폴더 선택 (개요=README.md)")
    out.append("")
    out.append("## 프로젝트별 세션")
    out.append("")
    out.append("| 프로젝트 | 세션 수 | 기간 |")
    out.append("|---|---|---|")
    for p in projects:
        starts = [session_start(s) for s in p["sessions"] if session_start(s)]
        if starts:
            first = min(starts).strftime("%Y-%m-%d")
            last = max(starts).strftime("%Y-%m-%d")
            period = f"{first} ~ {last}"
        else:
            period = "-"
        out.append(f"| [{p['name']}](./{p['folder']}/README.md) | {len(p['sessions'])} | {period} |")
    out.append("")
    return "\n".join(out)


def build_viewer(out_dir):
    template = Path(__file__).resolve().parent / "viewer_template.html"
    if not template.exists():
        print(f"경고: 뷰어 템플릿을 찾지 못해 뷰어를 생성하지 않습니다: {template}")
        return None
    target = out_dir / "viewer.html"
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(template.read_text(encoding="utf-8"))
    return target


def main():
    parser = argparse.ArgumentParser(description="Codex 세션을 프로젝트별 Markdown으로 내보내기")
    parser.add_argument("--sessions-dir", action="append", default=None, metavar="DIR",
                        help="세션 JSONL 폴더 (여러 번 지정 가능). 미지정 시 표준 + Orca 경로 자동 탐색")
    parser.add_argument("-o", "--output", default="codex_export", help="내보낼 폴더 (기본: ./codex_export)")
    parser.add_argument("--include-tool-output", action="store_true", help="도구 실행 출력 포함")
    parser.add_argument("--no-viewer", action="store_true", help="웹 뷰어 생성 생략")
    args = parser.parse_args()

    if args.sessions_dir:
        session_dirs = [Path(p) for p in args.sessions_dir]
    else:
        session_dirs = discover_session_dirs()
    session_dirs = [d for d in session_dirs if d.exists()]
    if not session_dirs:
        print("세션 폴더를 찾지 못했습니다. --sessions-dir로 경로를 지정하세요.")
        return 1

    files = []
    for d in session_dirs:
        found = list(d.rglob("rollout-*.jsonl"))
        files.extend(found)
        print(f"  {source_label(d)}: 세션 파일 {len(found)}개")
    if not files:
        print(f"세션 파일을 찾지 못했습니다: {', '.join(str(d) for d in session_dirs)}")
        return 1

    sessions = load_all_sessions(session_dirs)
    print(f"세션 파일 {len(files)}개 발견, 고유 세션 {len(sessions)}개 로드")

    grouped = {}
    for sess in sessions:
        cwd = sess["meta"].get("cwd")
        key = os.path.normcase(os.path.normpath(cwd.strip().rstrip("/\\"))) if cwd else None
        grouped.setdefault(key, []).append(sess)

    folders = assign_folder_names(list(grouped))

    out_dir = Path(args.output)
    projects_dir = out_dir / "projects"

    project_infos = []
    total_assets = 0
    for key, sess_list in grouped.items():
        folder = folders[key]
        cwd = sess_list[0]["meta"].get("cwd") or key
        pdir = projects_dir / folder
        pdir.mkdir(parents=True, exist_ok=True)
        used_names = set()
        for sess in sess_list:
            start = session_start(sess)
            slug = INVALID_FS_CHARS.sub("_", title_for(sess["events"]))
            slug = re.sub(r"\s+", "_", slug)[:50].strip("_. ")
            stem = start.strftime("%Y-%m-%d_%H%M%S") if start else str(sess["path"].stem)[:16]
            base = f"{stem}_{slug}" if slug else stem
            filename = f"{base}.md"
            if filename in used_names:
                filename = f"{base}_{sess['path'].stem.split('-')[-1][:8]}.md"
            used_names.add(filename)
            sess["filename"] = filename

            assets = collect_assets(sess["events"])
            asset_names = []
            for n, (data, ext) in enumerate(assets, 1):
                total_assets += 1
                name = f"{stem}_img_{n}.{ext}"
                asset_names.append(name)
                (pdir / "assets").mkdir(exist_ok=True)
                (pdir / "assets" / name).write_bytes(data)
            sess["asset_names"] = asset_names

            try:
                rel = os.path.relpath(sess["path"], next(d for d in session_dirs if str(sess["path"]).lower().startswith(str(d).lower())))
            except (StopIteration, ValueError):
                rel = str(sess["path"])
            md = render_session_markdown(sess, rel, args.include_tool_output)
            with open(pdir / filename, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(md)

        proj_readme = build_project_readme(folder, cwd, sess_list)
        with open(pdir / "README.md", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(proj_readme)
        project_infos.append({"name": folder, "folder": folder, "sessions": sess_list, "cwd": cwd})

    project_infos.sort(key=lambda p: -len(p["sessions"]))
    top = build_top_readme(project_infos, sessions, session_dirs, args.include_tool_output)
    with open(projects_dir / "README.md", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(top)

    if not args.no_viewer:
        viewer = build_viewer(out_dir)
        if viewer:
            print(f"뷰어: {viewer}")

    print(f"완료: {len(sessions)}개 세션, {len(grouped)}개 프로젝트 -> {out_dir}")
    for p in project_infos:
        print(f"  {p['folder']}: {len(p['sessions'])}개 세션")
    if total_assets:
        print(f"이미지 {total_assets}개 추출")
    return 0


if __name__ == "__main__":
    sys.exit(main())
