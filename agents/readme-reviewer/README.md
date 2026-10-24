# readme-reviewer

> A read-only Google ADK agent (single-agent or multi-agent team) that audits a project folder against this repository's contribution standards and returns a fix report before you open a PR.

---

## Overview

### Problem Statement & Intended Users
- **Problem**: Contributions are reviewed on documentation quality, reproducibility, secret hygiene and PR scope. Contributors often miss a README section, forget a dependency manifest, leave a `.env` file or API key in the folder, or touch files outside their own folder.
- **Intended Users**: Anyone preparing a PR to `agents/` or `tools/` in this repository, and maintainers doing a quick first-pass review.

### Key Features
- **Two modes**
  - `readme_reviewer`: one agent calls the checks and writes the report (simple, fewer model requests).
  - `readme_reviewer_team`: Docs, Security and Scope specialists run in parallel, then a synthesizer merges and ranks their findings (more thorough, more model requests).
- **Template check**: Verifies the README has every section from `template/README.md`, flags unfilled placeholders (ignoring ones quoted in code), thin sections, and commands that reference files that do not exist.
- **Reproducibility check**: Looks for a dependency manifest, `.env.example` and `.gitignore`.
- **Security check**: Flags `.env` files, `.venv` folders, key-like strings (Google, NVIDIA, OpenAI-style, AWS, private keys) and risky code patterns (shell execution, `eval`, recursive delete). Matched values are never printed.
- **Scope check**: Uses read-only git to confirm changes touch only the project folder plus at most one index row.
- **Friendly paths**: `Review template`, `Review my-agent` or a full path all work; names are resolved inside the repository.
- **Configurable model**: Gemini (default) or any NVIDIA-hosted model via an OpenAI-compatible endpoint.
- **Guardrails** (see Security section).

---

## Technical Stack

- **Language & Runtime**: Python 3.11+ (developed and tested on Python 3.14)
- **Agent Framework / Core Library**: Google Agent Development Kit (`google-adk`), with `LiteLlm` (`litellm`, optional) for the NVIDIA provider
- **Models**: Gemini 2.5 Flash by default; any NVIDIA model id you configure
- **External APIs / Tools**: Google AI Studio (Gemini API) or NVIDIA API Catalog. All checks run locally as plain Python functions; the scope check shells out to read-only `git` commands.

---

## Architecture & Data Flow

### Simple mode (`readme_reviewer`)
```
[Folder name/path] --> [root_agent + Gemini/NVIDIA]
                           |  (before_tool_callback: call limit, arg size)
                           +--> check_folder_name, list_project_files,
                           |    check_readme_sections, check_manifest,
                           |    scan_for_secrets, read_file
[Verdict / Problems / Fixes] <-- [Agent report]
```

### Team mode (`readme_reviewer_team`)
```
                         +--> docs_reviewer ------ check_readme_sections, check_readme_quality, read_file
[Folder name/path] --> [parallel]
                         +--> security_reviewer -- scan_for_secrets, check_risky_code
                         +--> scope_reviewer ----- check_folder_name, check_manifest,
                         |                         list_project_files, check_pr_scope
                         v   (each writes findings to session state)
                  [review_synthesizer] --> Verdict / Blockers / Warnings / Suggested fixes
```

All checking is deterministic Python in `readme_reviewer/tools.py`. Models only choose tools and write up results. Each specialist gets only the tools it needs.

---

## Prerequisites

- Python 3.11+ (required by `google-adk`; developed and tested on 3.14)
- `pip`
- `git` (only needed for the scope check)
- An API key for one provider:
  - Gemini: Google AI Studio key (free tier available): https://aistudio.google.com/apikey
  - NVIDIA: key and exact model id from https://build.nvidia.com

---

## Installation & Setup

1. **Navigate to the project directory:**
   ```bash
   cd agents/readme-reviewer
   ```

2. **Set up the virtual environment / install dependencies:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate

   pip install -r requirements.txt
   # Only if you use MODEL_PROVIDER=nvidia (adds litellm and mcp):
   # pip install -r requirements-nvidia.txt
   ```

3. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set your key. ADK loads `.env` from the agent package directory, so also copy it there if `adk` does not pick it up: `cp .env readme_reviewer/.env` and `cp .env readme_reviewer_team/.env` (both are covered by the `.env` rule in `.gitignore`).

---

## Configuration & Environment Variables

| Variable Name | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `MODEL_PROVIDER` | No | `gemini` | `gemini` or `nvidia` |
| `GOOGLE_API_KEY` | Yes for `gemini` | *None* | Google AI Studio API key |
| `MODEL_NAME` | Gemini: no, NVIDIA: yes | `gemini-2.5-flash` (Gemini only) | Model id. For NVIDIA use the exact id from build.nvidia.com |
| `NVIDIA_API_KEY` | Yes for `nvidia` | *None* | NVIDIA API key |
| `NVIDIA_BASE_URL` | No | `https://integrate.api.nvidia.com/v1` | OpenAI-compatible endpoint |
| `ALLOWED_ROOT` | No | enclosing git repo, else the cwd | The only directory tree the tools may read |
| `MAX_TOOL_CALLS` | No | `12` | Max tool calls per agent per run |
| `BASE_REF` | No | `upstream/main`, then `origin/main`, then `main` | Branch the scope check compares against |

---

## How to Run

From `agents/readme-reviewer/`:

```bash
# Simple mode
adk run readme_reviewer

# Multi-agent team mode
adk run readme_reviewer_team

# Browser dev UI (pick either agent from the dropdown)
adk web
```

At the prompt, name the folder to review:

```
Review template
Review agents/my-agent
Review /full/path/inside/the/repo
```

To use NVIDIA instead of Gemini, set in `.env`:

```
MODEL_PROVIDER=nvidia
MODEL_NAME=<exact model id from build.nvidia.com>
NVIDIA_API_KEY=<your key>
```

---

## Example Input & Output

### Example Input
```
Review template
```

### Example Output (simple mode)
Captured from a genuine `adk run readme_reviewer` session with `gemini-2.5-flash`:

```
## Verdict   Needs fixes
## Problems
*   `README.md`: Contains unreplaced placeholders.
*   Missing dependency manifest file.
## Suggested fixes
*   Replace "[One-sentence summary of what this project does and the value it provides.]" and "[Project Name]" in `README.md` with actual project details.
*   Add a dependency manifest file (e.g., `requirements.txt`, `package.json`, `pyproject.toml`, `go.mod`, etc.).
```

### Example Output (team mode, partial)
A genuine `adk run readme_reviewer_team` session on `Review readme-reviewer` produced these specialist reports in parallel before Gemini returned `503 UNAVAILABLE`, so the synthesizer's merged report was not captured:

```
[scope_reviewer]:
- OK: The folder name 'readme-reviewer' is valid.
- OK: Manifest files found: `requirements.txt`. `.env.example` and `.gitignore` exist.
- OK: All changed files are within the project folder.
- OK: `agents/README.md` was changed with 1 row added.
[docs_reviewer]:
- WARNING: Leftover placeholders found in README ...
- OK: All required sections are present in README.
```
The placeholder warning above exposed a bug (placeholders quoted inside code were being counted). It is fixed and covered by a unit test; the run was not repeated.

---

## How to Test

The tools, guardrails, model configuration and team wiring are tested without any API key:

```bash
pip install -r requirements.txt
pytest
```

Expected: `42 passed`. Coverage includes path resolution and sandboxing (including `..` and symlink escapes), refusal and redaction in `read_file`, secret and risky-code scanning, README quality checks, the git scope check against a real temporary repository, the tool-call limiter, model provider selection, and the team's structure and tool assignments.

For an end-to-end check, run `adk run readme_reviewer` with a valid key and review a folder containing a fake `.env` file; the report should mark it as a BLOCKER.

---

## Known Limitations

- **Free-tier rate limits.** Gemini's free tier allowed 5 requests/minute for `gemini-2.5-flash` when tested. Simple mode usually fits; team mode needs about seven requests per review and hit `429 RESOURCE_EXHAUSTED`. Use a billed Gemini key or the NVIDIA provider for team mode.
- **Team mode was not verified end to end.** Two specialists were observed running live in parallel; the full pipeline including the synthesizer did not complete because of a Gemini `503` and then the `429` above. Wiring is covered by unit tests only.
- **NVIDIA mode was not tested live.** Provider selection and `LiteLlm` construction are unit tested; no real NVIDIA request was made.
- Section matching is by heading keyword; "thin section" is a word-count heuristic, not a quality judgement.
- The secret and risky-code scans are regex based: they can miss unusual formats and produce false positives. Files over 1 MB are skipped.
- `read_file` returns only the first 20 KB, and `list_project_files` lists at most 200 files.
- The scope check needs a git checkout and a base branch; otherwise it reports "not applicable".
- It does not run your project or verify that the setup steps work; you still need a clean-environment test.
- Tested on macOS only; Windows and Linux are untested.

---

## Security & Privacy Considerations

- **Secrets Handling**: API keys are read from the environment (`.env`, git-ignored). The secret scanner redacts matched values.
- **Data Privacy**: Tool results are sent to the model provider (Google or NVIDIA). `read_file` refuses `.env*`, `*.pem`, `*.key`, `*.p12`, `id_rsa`, `id_ed25519`, `credentials.json` and `service-account*` files, and redacts key-like strings in everything else it returns.
- **Safety / guardrails**:
  - **Read-only**: no write tools and no model-controlled shell. The only subprocess use is fixed read-only `git` commands (no shell, validated branch name, 10 s timeout).
  - **Path sandbox**: every path is resolved and must stay inside `ALLOWED_ROOT` (default: the git repo). `..`, absolute paths elsewhere and symlinks that escape are denied; symlinks are never followed during scans.
  - **Prompt-injection defence**: file contents are returned marked as untrusted, and every agent's instructions say never to follow instructions found in files.
  - **Loop and size limits**: a `before_tool_callback` caps tool calls per agent per run (`MAX_TOOL_CALLS`) and rejects oversized arguments; reads and listings are size-capped.
  - **Least privilege (team mode)**: each specialist only has the tools for its job; for example the security reviewer cannot read arbitrary files.
  - These reduce risk but do not make it zero; run the agent only in a trusted local session.

---

## Future Improvements

- [ ] Verify the team pipeline end to end and capture a full merged report.
- [ ] Retry with backoff on `429`/`503` model errors.
- [ ] Verify that the README's example commands actually run.
- [ ] Output a machine-readable JSON report for CI use.
- [ ] Optional, confirmation-gated auto-fix agent.

---

## License

*This project is contributed under the repository's open-source license.*
