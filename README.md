# codex-export-to-md

**한국어** · [English](#english)

Codex CLI 세션 기록을 프로젝트 폴더별 Markdown으로 내보내고, 단일 파일 웹 뷰어를 함께 생성하는 Python 스크립트입니다.

---

## 한국어

### 소개

Codex CLI는 세션 기록을 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` 형태로 저장합니다. 이 도구는 표준 경로와 Orca 앱의 codex-home 경로를 모두 탐색해 세션을 수집하고, 같은 세션은 중복 제거한 뒤, 당시 작업 폴더(cwd)를 기준으로 프로젝트별로 묶어 읽기 좋은 Markdown으로 변환합니다.

함께 생성되는 `viewer.html`은 외부 라이브러리 없이 동작하는 단일 파일 웹 뷰어로, 내보낸 `projects` 폴더를 열어 대화를 탐색할 수 있습니다.

### 누락 없이 백업하기

```powershell
python codex_export.py --project 'D:\DEV\WEB\suho-kakao-relay' --include-tool-output --max-output-chars 0 --backup-raw -o 'backups/suho-kakao-relay'
```

- `--project`는 작업 폴더와 그 하위 폴더를 선택합니다. Windows의 `\\?\` 접두사, 슬래시 및 대소문자 차이를 정규화합니다.
- 기본 탐색은 `CODEX_HOME`, 표준 및 Orca 홈의 `sessions`와 `archived_sessions`를 포함합니다. 다른 PC/WSL의 기록은 해당 폴더를 복사하여 `--sessions-dir`로 추가해야 합니다.
- 스레드 고유 `id`를 우선 사용합니다. 하위 에이전트는 부모와 `session_id`가 같을 수 있으므로 이를 중복으로 제거하면 안 됩니다.
- 인접한 `state_*.sqlite`에서 `/resume` 제목을 읽고, `thread_history_*.sqlite`에만 있는 사용자/Codex 메시지를 별도 보완 구역에 기록합니다. SQLite만 존재하고 JSONL 파일이 없는 스레드를 자동으로 생성하지는 않습니다.
- `--max-output-chars 0`은 Markdown의 도구 출력 길이 제한을 해제합니다. 원본이 이미 잘린 출력이나 암호화된 내용까지 평문으로 복구하지는 않습니다.
- `--backup-raw`는 중복 사본을 포함한 선택된 원본 JSONL 전체, 해당 홈의 `state_*.sqlite`와 `thread_history_*.sqlite` 전체 스냅샷, SHA-256 목록인 `backup_manifest.json`을 저장합니다. DB 스냅샷은 다른 프로젝트의 기록도 포함합니다. SQLite backup API로 커밋된 WAL 내용도 포함합니다.
- Markdown은 읽기용 변환본입니다. 압축 전 메시지, 지원하지 않는 이벤트, 암호화된 에이전트 메시지 등을 보존하려면 `raw/`도 함께 보관하세요. 외부 파일 경로로만 참조된 첨부파일과 인증 정보는 이 백업에 포함되지 않습니다.
- 실행 중인 세션은 계속 바뀔 수 있습니다. 최종 백업은 대상 세션의 응답이 끝난 뒤 새 출력 폴더에 실행하세요. JSONL과 여러 DB 전체를 하나의 원자적 시점으로 묶는 기능은 없습니다.
- 메타데이터만 있고 JSONL/SQLite 어디에도 본문이 없으면 경고합니다. 이 경우 이전 백업이나 다른 환경의 원본이 필요합니다.

### 주요 기능

- **세션 소스 자동 탐색** — 표준 `~/.codex`, `CODEX_HOME` 및 Orca 경로(`~/.codex-*`, `%APPDATA%\\Orca\\codex-runtime-home`, `%APPDATA%\\Orca\\codex-accounts`)에서 `sessions`와 `archived_sessions`를 탐색합니다.
- **중복 제거** — 동일한 스레드 `id`(없으면 `session_id`)를 가진 파일은 가장 큰 파일 하나를 Markdown에 사용합니다. 원본 백업에는 모든 사본을 보존합니다.
- **프로젝트별 정리** — 세션을 당시 작업 폴더(cwd) 기준으로 그룹화하고, 폴더명이 겹치면 상위 경로를 붙여 구분합니다.
- **읽기 좋은 Markdown** — 사용자/Codex 발화, 진행 메모(코멘터리), 도구 호출(접기 가능한 `<details>`), 세션 메타(시작 시각, 모델, Git 브랜치·커밋·저장소, CLI 버전, 세션 ID)를 정리해 담습니다.
- **첨부 이미지 추출** — 대화에 포함된 base64 인라인 이미지를 `assets/` 폴더에 파일로 저장하고 Markdown에서 참조합니다.
- **웹 뷰어 생성** — 의존성 없는 단일 `viewer.html`을 생성합니다(폴더 열기, 사이드바, 검색, 이전/다음 탐색, 라이트·다크 테마 지원).
- **외부 패키지 불필요** — Python 표준 라이브러리만 사용합니다.

### 요구 사항

- Python 3.7 이상
- 웹 뷰어 사용 시 최신 브라우저(폴더 선택 API는 Chrome/Edge 계열 권장, 미지원 브라우저는 폴더 업로드 방식으로 동작)

### 사용법

```bash
python codex_export.py
```

기본값으로 현재 폴더의 `codex_export/`에 내보내고 `viewer.html`을 생성합니다.

```bash
# 특정 세션 폴더 지정 (여러 번 지정 가능) + 출력 폴더 지정
python codex_export.py --sessions-dir "C:\\Users\\me\\.codex\\sessions" -o export

# 도구 실행 출력까지 포함하여 내보내기
python codex_export.py --include-tool-output

# 웹 뷰어 생성 생략
python codex_export.py --no-viewer
```

### 옵션

| 옵션 | 설명 |
|---|---|
| `--sessions-dir DIR` | 세션 JSONL 폴더. 여러 번 지정 가능. 미지정 시 표준 `~/.codex`, `CODEX_HOME` 및 Orca 경로에서 활성·보관 세션을 자동 탐색합니다. |
| `-o, --output DIR` | 내보낼 폴더. 기본값: `./codex_export` |
| `--include-tool-output` | 도구 호출(쉘 명령 등)의 실행 출력도 포함합니다. 기본값은 미포함입니다. |
| `--no-viewer` | 웹 뷰어(`viewer.html`) 생성을 생략합니다. |
| `--project CWD` | 특정 작업 폴더와 하위 폴더의 세션만 선택합니다. |
| `--backup-raw` | 원본 사본, SQLite 스냅샷 및 SHA-256 검증 목록을 보관합니다. |
| `--max-output-chars N` | 도구 출력 길이 제한. 기본 30,000자, `0`은 무제한입니다. |

### 출력 구조

```
codex_export/
├── viewer.html              # 단일 파일 웹 뷰어
├── backup_manifest.json     # --backup-raw 사용 시: 출처, SHA-256, 세션 목록
├── raw/                     # --backup-raw 사용 시: 원본 JSONL 사본 및 SQLite 스냅샷
└── projects/
    ├── README.md            # 전체 개요 (프로젝트별 세션 수, 기간)
    └── <프로젝트 폴더>/
        ├── README.md        # 프로젝트별 세션 목록
        ├── assets/          # 대화에서 추출한 첨부 이미지
        └── <YYYY-MM-DD_HHMMSS>_<ID 접미사>_<제목>.md   # 세션 대화 기록
```

### 세션 Markdown 구성

각 세션 파일은 다음과 같이 구성됩니다.

- `/resume` 제목(없으면 첫 사용자 메시지에서 추출한 제목)과 출처(원본 JSONL 경로). 파일명의 제목은 첫 사용자 메시지를 기준으로 합니다.
- 메타 정보 표: 시작 시각, Codex 제목, 부모 세션(있는 경우), 프로젝트(cwd), Git 브랜치·커밋·저장소, 모델, CLI 버전, 세션 ID
- `#### 🧑 사용자` / `#### 🤖 Codex` 발화와 타임스탬프
- `> 💬 진행 메모`로 표시되는 코멘터리(중간 진행 메시지)
- 도구 호출은 `<details>`로 접힘, `--include-tool-output` 사용 시 실행 출력 포함(기본 30,000자, `--max-output-chars 0`으로 제한 해제)
- 컨텍스트 압축(compaction)이 있던 지점에는 안내 문구 표시
- SQLite에만 있는 사용자/Codex 메시지는 출처를 명시한 별도 보완 구역에 표시
- 에이전트 간 메시지와 암호화된 본문이 있다는 안내 표시
- `<environment_context>`만 있는 사용자 메시지는 제외하고, 도구 출력의 ANSI 이스케이프 시퀀스는 정리

### 웹 뷰어 사용 방법

1. `viewer.html`을 브라우저에서 엽니다.
2. **폴더 열기** 버튼으로 내보낸 `projects` 폴더를 선택합니다.
3. 사이드바에서 프로젝트와 세션을 탐색하거나 검색하고, `projects/README.md`는 **개요** 메뉴에서 확인할 수 있습니다.

---

## English

### Introduction

A Python script that exports Codex CLI session logs into per-project Markdown and generates a single-file web viewer. Codex CLI stores sessions as `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. This tool scans both the standard path and Orca app codex-home paths, deduplicates identical sessions, groups them by the working directory (cwd) they were run in, and converts them into readable Markdown.

The generated `viewer.html` is a dependency-free, single-file web viewer for browsing the exported `projects` folder.

### Backing up without omissions

```powershell
python codex_export.py --project 'D:\DEV\WEB\suho-kakao-relay' --include-tool-output --max-output-chars 0 --backup-raw -o 'backups/suho-kakao-relay'
```

- `--project` selects a working directory and its subdirectories. Windows `\\?\` prefixes, slash styles, and case differences are normalized.
- Automatic discovery includes `sessions` and `archived_sessions` under `CODEX_HOME`, the standard home, and Orca homes. For records from another PC or WSL, copy the relevant folders and add them with `--sessions-dir`.
- The unique thread `id` takes precedence. Child agents can share their parent's `session_id`, so using that field alone would incorrectly remove their records as duplicates.
- Adjacent `state_*.sqlite` databases supply `/resume` titles. User/Codex messages found only in `thread_history_*.sqlite` are placed in a separate supplement. Threads with SQLite records but no JSONL file are not automatically reconstructed.
- `--max-output-chars 0` removes the Markdown tool output length limit. It cannot recover already-truncated output or decrypt encrypted content into plaintext.
- `--backup-raw` saves every selected original JSONL copy, including duplicates; full snapshots of that home's `state_*.sqlite` and `thread_history_*.sqlite` databases; and a SHA-256 inventory in `backup_manifest.json`. Database snapshots also include other projects. The SQLite backup API includes committed WAL data.
- Markdown is a readable conversion. Keep `raw/` as well to preserve messages from before compaction, unsupported events, and encrypted agent messages. Attachments referenced only by external file paths and credentials are not included in this backup.
- Active sessions can keep changing. For the final backup, wait until the target session's response finishes and use a new output folder. JSONL files and multiple databases are not captured at one atomic point in time.
- The exporter warns if a session has metadata but no conversation body in either JSONL or SQLite. Such records require an earlier backup or originals from another environment.

### Features

- **Automatic session discovery** — scans `sessions` and `archived_sessions` under the standard `~/.codex` home, `CODEX_HOME`, and Orca paths (`~/.codex-*`, `%APPDATA%\\Orca\\codex-runtime-home`, `%APPDATA%\\Orca\\codex-accounts`).
- **Deduplication** — Markdown uses the largest file for each unique thread `id` (falling back to `session_id`). Raw backups preserve all copies.
- **Per-project organization** — sessions are grouped by their working directory (cwd); conflicting folder names get parent-path prefixes.
- **Readable Markdown** — user/Codex messages, commentary (progress notes), tool calls (collapsible `<details>`), and session metadata (start time, model, Git branch/commit/repo, CLI version, session ID).
- **Image extraction** — base64 inline images in conversations are saved as files under `assets/` and referenced from Markdown.
- **Web viewer generation** — produces a single `viewer.html` (folder opening, sidebar, search, prev/next navigation, light/dark theme).
- **No external packages** — uses only the Python standard library.

### Requirements

- Python 3.7+
- A modern browser for the viewer (the folder-picker API works best in Chrome/Edge; unsupported browsers fall back to folder upload)

### Usage

```bash
python codex_export.py
```

By default this exports to `codex_export/` in the current directory and generates `viewer.html`.

```bash
# Specify session folders (repeatable) and an output folder
python codex_export.py --sessions-dir "C:\\Users\\me\\.codex\\sessions" -o export

# Include tool execution output
python codex_export.py --include-tool-output

# Skip generating the web viewer
python codex_export.py --no-viewer
```

### Options

| Option | Description |
|---|---|
| `--sessions-dir DIR` | Session JSONL folder. Repeatable. If omitted, active and archived sessions are discovered under the standard `~/.codex` home, `CODEX_HOME`, and Orca paths. |
| `-o, --output DIR` | Output folder. Default: `./codex_export` |
| `--include-tool-output` | Also include tool call execution output (shell commands, etc.). Off by default. |
| `--no-viewer` | Skip generating the web viewer (`viewer.html`). |
| `--project CWD` | Select sessions from a working directory and its subdirectories. |
| `--backup-raw` | Preserve original copies, SQLite snapshots, and a SHA-256 inventory. |
| `--max-output-chars N` | Tool output length limit. Default: 30,000 characters; `0` means unlimited. |

### Output layout

```
codex_export/
├── viewer.html              # single-file web viewer
├── backup_manifest.json     # with --backup-raw: sources, SHA-256 hashes, session list
├── raw/                     # with --backup-raw: original JSONL copies and SQLite snapshots
└── projects/
    ├── README.md            # global overview (session counts, date ranges)
    └── <project folder>/
        ├── README.md        # per-project session list
        ├── assets/          # extracted attachment images
        └── <YYYY-MM-DD_HHMMSS>_<ID suffix>_<title>.md   # session transcript
```

### Session Markdown structure

Each session file contains:

- The `/resume` title (falling back to the first user message), plus the source (original JSONL path). The title in the filename is derived from the first user message.
- A metadata table: start time, Codex title, parent session (when available), project (cwd), Git branch/commit/repo, model, CLI version, session ID
- `#### 🧑 User` / `#### 🤖 Codex` messages with timestamps
- Commentary (intermediate progress messages) shown as `> 💬 Progress note`
- Tool calls rendered as collapsible `<details>`; with `--include-tool-output`, execution output is included (default limit: 30,000 characters; use `--max-output-chars 0` to remove it)
- A notice wherever context compaction occurred
- A separate supplement identifying user/Codex messages found only in SQLite
- Inter-agent messages and notices identifying encrypted message bodies
- User messages containing only `<environment_context>` are omitted; ANSI escape sequences are removed from tool output

### Using the web viewer

1. Open `viewer.html` in your browser.
2. Click **Open folder** and select the exported `projects` folder.
3. Browse or search projects and sessions in the sidebar; `projects/README.md` appears under the **Overview** menu.
