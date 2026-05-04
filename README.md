# כלי ניהול קולות קוראים — Lavivi RFP Intake

CLI tool that ingests a call-for-proposals URL (or PDF), uses Claude to extract
structured data, and creates a fully-populated item + subitems in the
**Resources for Growing** board on Monday.com.

The tool encodes the team's working patterns and prevents the intake-data
issues that previously plagued the board (missing deadlines, empty Submission
Analysis, conflicting executor columns, broken hours formula).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in ANTHROPIC_API_KEY and MONDAY_API_KEY
```

The `MONDAY_API_KEY` needs `boards:read`, `boards:write` scopes.

## Usage

```bash
# interactive: preview, confirm, create
python intake.py --url https://example.org/grant

# accept a local PDF instead
python intake.py --file proposal.pdf

# skip the confirmation prompt
python intake.py --url <url> --yes

# pre-assign an executor to all subitems
python intake.py --url <url> --executor "לביא"

# print analysis only, do not call Monday
python intake.py --url <url> --dry-run

# refresh column/group IDs from the live board
python intake.py --refresh-config
```

## What the tool guarantees

- The new item lands in **מקורות מישראל** or **מקורות מחו"ל** based on origin.
- `סוג הבקשה` is always `הגשה למענק/קול קורא`.
- `השלב שלנו` always starts at `בדיקת התאמה`.
- The deadline column is **required** — creation aborts if Claude cannot
  extract one.
- `Submission Analysis` is always populated.
- Every subitem has hours filled (so the `DONE*כמות שעות` formula works).
- Only `dropdown_mkxrnxep` is used for "מבצע בפועל"; the duplicate
  `color_mkxrf6kb` and the always-empty `color_mkxra7wc` are never written.

## Tests

```bash
pytest tests/
```
