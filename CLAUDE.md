# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Windows-only Python desktop automation tool that solves "蓄意战败" (intentional defeat) quizzes in 王者荣耀 (Honor of Kings). It reads quiz content by simulating Ctrl+A/Ctrl+C and parsing the clipboard's HTML format, then answers via a knowledge base or brute-force traversal.

## Commands

```bash
# Install dependencies (Windows required)
pip install -r requirements.txt

# Run the main solver
python auto_solver_refactored.py

# Capture screen region coordinates (run first to configure SCREEN_REGION)
python tools/get_region_tool.py

# Merge learned answers from solution_map.json files into the master QA bank
python tools/merge_tool.py

# Diagnose clipboard HTML content (troubleshooting tool)
python tools/test_rtf_parser.py
```

## Architecture

The project is a single-script system (`auto_solver_refactored.py`, ~950 lines) with supporting tools:

**Core loop:** Ctrl+A → Ctrl+C on the target region → parse clipboard HTML via `BeautifulSoup` → match against `master_qa_bank.json` → if no match, brute-force try option combinations → click submit → detect next question via content change.

**Key data flow:**
1. `master_qa_bank.json` — persistent knowledge base loaded at startup. Structure: `{question_text: [{options: [...], answer: [...]}, ...]}`. Supports multiple variants per question (same question, different option sets).
2. `screenshots/<timestamp>/solution_map.json` — per-run learned answers. Merge into master via `tools/merge_tool.py`.
3. `templates/` — small screenshots of option icons (A/B/C/D) and the submit button, used by OpenCV + airtest `Template` matching for click positioning. The solver does NOT OCR with these; it only uses them to find click coordinates.

**Solver modes (in priority order):**
- **QA bank mode:** Matches question text + option set against known answers. Requires exact option-set match to handle variants.
- **Fallback/traversal mode:** Single-choice — try each option one by one. Multi-choice — try all combinations from size 2 upward.
- **Verify-and-click:** After clicking options, re-reads clipboard HTML to confirm the `active` CSS class is present on the expected `<li>` elements. Retries up to `max_retries` times.

**Critical Windows dependency:** `win32clipboard` accesses the "HTML Format" clipboard format (registered as `HTML Format`). This is why the tool requires Windows — clipboard HTML is not available on other platforms. `IS_WINDOWS` flag gates all HTML-based features; without it, the solver falls back to plain-text parsing and blind clicking.

**Configuration:** All tunable parameters are at the top of `auto_solver_refactored.py` — screen region, similarity thresholds, scroll mode, delays, retry counts. `SCREEN_REGION` must be set per-machine using `get_region_tool.py`.

## Notable implementation details

- Question detection relies on HTML class names: `ts_title_count` (question number/type), `ts_title_text` (question body), `options-wrapper` (options list), `active` class on `<li>` (selected state). These are specific to the 腾讯游戏安全中心 WeChat mini-program's DOM.
- Image-type options store their `src` URL as the option content rather than text.
- Failed HTML parses are saved to `logs/failed_parse_<timestamp>.html` for debugging.
- `requirements.txt` is missing `pyperclip` — the main script imports it but the dependency isn't listed.