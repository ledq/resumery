#!/usr/bin/env python3
"""Create or reuse the application workspace for one JD; code owns naming and identity.

Reuse: the latest non-terminal applications/<id>/ matching the posting URL, else
company+role (run-scoped files reset, .run/parsed_jd.json kept). Create:
applications/<date>_<company>_<role>/ ('untitled' fallback, -2/-3 on collision).
jd.txt is the workspace marker: only this script writes it. A `url` file beside
--jd-file, when present, is persisted to .run/posting_url.

usage : new_workspace.py --jd-file PATH [--company S] [--role S]
stdout: the workspace path, alone on the last line
exit  : 0 ok / 2 no readable JD
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
APPS = BASE / "applications"

# Files a fresh run must not inherit on reuse; .run/parsed_jd.json survives.
RUN_SCOPED = [
    ".run/resume.json", ".run/resume.tex", ".run/run.json",
    ".run/review_notes.md", ".run/review_reverify.md", ".run/fix_notes.md",
    "gaps.md",
]
TERMINAL_STATUSES = {"offer", "rejected"}


def slug(text, maxlen=40):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:maxlen].strip("-")


def norm_url(u):
    return (u or "").strip().rstrip("/").lower() or None


def status_of(ws):
    f = ws / "status"
    if f.exists():
        return f.read_text(encoding="utf-8").strip().lower()
    # No declared status: a folder holding a resume was tailored; bare jd/parse = saved.
    if (ws / ".run" / "run.json").exists() or (ws / ".run" / "resume.json").exists():
        return "tailored"
    return "saved"


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def posting_url_of(ws):
    """The workspace's posting URL: the code-owned file, else a legacy parsed_jd field."""
    f = ws / ".run" / "posting_url"
    if f.exists():
        return f.read_text(encoding="utf-8").strip() or None
    return load_json(ws / ".run" / "parsed_jd.json").get("posting_url")


def find_match(url, company, role):
    """Most recent non-terminal application matching posting URL, else company+role."""
    url = norm_url(url)
    company = (company or "").strip().casefold() or None
    role = (role or "").strip().casefold() or None
    matches = []
    for ws in sorted(APPS.glob("*/")):
        if not (ws / "jd.txt").exists():
            continue  # not a marked workspace
        if status_of(ws) in TERMINAL_STATUSES:
            continue
        if url and norm_url(posting_url_of(ws)) == url:
            matches.append(ws)
            continue
        pj = load_json(ws / ".run" / "parsed_jd.json")
        pj_company = (pj.get("company") or "").strip().casefold()
        pj_role = (pj.get("role_title") or "").strip().casefold()
        if company and role and pj_company == company and pj_role == role:
            matches.append(ws)
    return matches[-1] if matches else None  # sorted + date-prefixed ids -> latest


def unique_dir(base_id):
    dest = APPS / base_id
    if not dest.exists():
        return dest
    n = 2
    while (APPS / f"{base_id}-{n}").exists():
        n += 1
    return APPS / f"{base_id}-{n}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jd-file", required=True)
    ap.add_argument("--company", default=None)
    ap.add_argument("--role", default=None)
    args = ap.parse_args()

    jd_path = Path(args.jd_file)
    try:
        jd = jd_path.read_text(encoding="utf-8").strip()
    except OSError as ex:
        sys.stderr.write(f"new_workspace.py: cannot read JD file: {ex}\n")
        return 2
    if not jd:
        sys.stderr.write(f"new_workspace.py: {jd_path} is empty; nothing to tailor.\n")
        return 2

    url_file = jd_path.parent / "url"
    url = url_file.read_text(encoding="utf-8").strip() if url_file.is_file() else None

    APPS.mkdir(exist_ok=True)

    ws = find_match(url, args.company, args.role)
    if ws is not None:
        for name in RUN_SCOPED:
            (ws / name).unlink(missing_ok=True)
        for pdf in ws.glob("Resume_*.pdf"):  # the named deliverable; name varies
            pdf.unlink()
        shutil.rmtree(ws / ".build", ignore_errors=True)
        (ws / ".run").mkdir(exist_ok=True)
        (ws / "jd.txt").write_text(jd + "\n", encoding="utf-8")
        sys.stderr.write(f"new_workspace.py: REUSED existing application {ws.name} "
                         "(run-scoped files reset; .run/parsed_jd.json kept)\n")
    else:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Failed extraction gets 'untitled' (collision suffix keeps it unique), never a
        # slug of the opening text: a line-less paste would misname the folder forever.
        base = "_".join(p for p in (slug(args.company), slug(args.role)) if p) or "untitled"
        ws = unique_dir(f"{date}_{base}")
        (ws / ".run").mkdir(parents=True)
        (ws / "jd.txt").write_text(jd + "\n", encoding="utf-8")
        sys.stderr.write(f"new_workspace.py: CREATED {ws.name}\n")

    if url:
        (ws / ".run" / "posting_url").write_text(url + "\n", encoding="utf-8")

    print(f"applications/{ws.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
