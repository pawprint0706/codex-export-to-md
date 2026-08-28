# codex-export-to-md

**한국어** · [English](#english)

Codex CLI 세션 기록을 프로젝트 폴더별 Markdown으로 내보내고, 단일 파일 웹 뷰어를 함께 생성하는 Python 스크립트입니다.

---

## 한국어

### 소개

Codex CLI는 세션 기록을 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` 형태로 저장합니다. 이 도구는 표준 경로와 Orca 앱의 codex-home 경로를 모두 탐색해 세션을 수집하고, 같은 세션은 중복 제거한 뒤, 당시 작업 폴더(cwd)를 기준으로 프로젝트별로 묶어 읽기 좋은 Markdown으로 변환합니다.

함께 생성되는 `viewer.html`은 외부 라이브러리 없이 동작하는 단일 파일 웹 뷰어로, 내보난 `projects` 폴더를 열어 대화를 탐색할 수 있습니다.

### 주요 기능

- **세션 소스 자동 탐색** — 표준 `~/.codex/sessions` 경로와 Orca 경로(`~/.codex-*/sessions`, `%APPDATA%\\Orca\\codex-runtime-home`, `%APPDATA%\\Orca\\codex-accounts`)를 모두 탐색합니다.
- **중복 제거** — 동일한 세션 ID를 가진 파일은 가장 큰 파일 하나만 사용합니다.
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
| `--sessions-dir DIR` | 세션 JSONL 폴더. 여러 번 지정 가능. 미지정 시 표준 `~/.codex` + Orca 경로를 자동 탐색합니다. |
| `-o, --output DIR` | 내보낼 폴더. 기본값: `./codex_export` |
| `--include-tool-output` | 도구 호출(쉘 명령 등)의 실행 출력도 포함합니다. 기본값은 미포함입니다. |
| `--no-viewer` | 웹 뷰어(`viewer.html`) 생성을 생략합니다. |

### 출력 구조

```
codex_export/
├── viewer.html              # 단일 파일 웹 뷰어
└── projects/
    ├── README.md            # 전체 개요 (프로젝트별 세션 수, 기간)
    └── <프로젝트 폴더>/
        ├── README.md        # 프로젝트별 세션 목록
        ├── assets/          # 대화에서 추출한 첨부 이미지
        └── <YYYY-MM-DD_HHMMSS>_<제목>.md   # 세션 대화 기록
```

### 세션 Markdown 구성

각 세션 파일은 다음과 같이 구성됩니다.

- 첫 사용자 메시지에서 추출한 제목과 출처(원본 JSONL 경로)
- 메타 정보 표: 시작 시각, 프로젝트(cwd), Git 브랜치·커밋·저장소, 모델, CLI 버전, 세션 ID
- `#### 🧑 사용자` / `#### 🤖 Codex` 발화와 타임스탬프
- `> 💬 진행 메모`로 표시되는 코멘터리(중간 진행 메시지)
- 도구 호출은 `<details>`로 접힘, `--include-tool-output` 사용 시 실행 출력 포함(30,000자 초과 시 잘림)
- 컨텍스트 압축(compaction)이 있던 지점에는 안내 문구 표시
- `<environment_context>` 블록과 ANSI 이스케이프 시퀀스는 자동으로 정리

### 웹 뷰어 사용 방법

1. `viewer.html`을 브라우저에서 엽니다.
2. **폴더 열기** 버튼으로 내보낸 `projects` 폴더를 선택합니다.
3. 사이드바에서 프로젝트와 세션을 탐색하거나 검색하고, `projects/README.md`는 **개요** 메뉴에서 확인할 수 있습니다.

---

## English

### Introduction

A Python script that exports Codex CLI session logs into per-project Markdown and generates a single-file web viewer. Codex CLI stores sessions as `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. This tool scans both the standard path and Orca app codex-home paths, deduplicates identical sessions, groups them by the working directory (cwd) they were run in, and converts them into readable Markdown.

The generated `viewer.html` is a dependency-free, single-file web viewer for browsing the exported `projects` folder.

### Features

- **Automatic session discovery** — scans the standard `~/.codex/sessions` path plus Orca paths (`~/.codex-*/sessions`, `%APPDATA%\\Orca\\codex-runtime-home`, `%APPDATA%\\Orca\\codex-accounts`).
- **Deduplication** — for files sharing the same session ID, only the largest file is used.
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
| `--sessions-dir DIR` | Session JSONL folder. Repeatable. If omitted, standard `~/.codex` + Orca paths are discovered automatically. |
| `-o, --output DIR` | Output folder. Default: `./codex_export` |
| `--include-tool-output` | Also include tool call execution output (shell commands, etc.). Off by default. |
| `--no-viewer` | Skip generating the web viewer (`viewer.html`). |

### Output layout

```
codex_export/
├── viewer.html              # single-file web viewer
└── projects/
    ├── README.md            # global overview (session counts, date ranges)
    └── <project folder>/
        ├── README.md        # per-project session list
        ├── assets/          # extracted attachment images
        └── <YYYY-MM-DD_HHMMSS>_<title>.md   # session transcript
```

### Session Markdown structure

Each session file contains:

- A title derived from the first user message, plus the source (original JSONL path)
- A metadata table: start time, project (cwd), Git branch/commit/repo, model, CLI version, session ID
- `#### 🧑 User` / `#### 🤖 Codex` messages with timestamps
- Commentary (intermediate progress messages) shown as `> 💬 Progress note`
- Tool calls rendered as collapsible `<details>`; with `--include-tool-output`, execution output is included (truncated past 30,000 characters)
- A notice wherever context compaction occurred
- Automatic cleanup of `<environment_context>` blocks and ANSI escape sequences

### Using the web viewer

1. Open `viewer.html` in your browser.
2. Click **Open folder** and select the exported `projects` folder.
3. Browse or search projects and sessions in the sidebar; `projects/README.md` appears under the **Overview** menu.
