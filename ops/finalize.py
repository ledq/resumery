#!/usr/bin/env python3
"""Close-out sweep: derive the human-facing layers from what the folders hold.

Per marked workspace: README.md rewritten when stale, the shipped PDF lifted to
<ws>/Resume_<Name>[_<Company>].pdf, a ledger row ensured in applications/run_log.tsv
(keyed by timestamp + id, so re-running never duplicates). Globally:
applications/index.md regenerated wholesale, never upserted. Idempotent; the no-arg
form is the Stop-hook sweep and self-heals runs whose hook never fired.

usage : finalize.py [<workspace>]   (no arg: sweep every workspace)
"""
import json
import re
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
APPS = BASE / "applications"
INDEX = APPS / "index.md"
LEDGER = APPS / "run_log.tsv"

LEDGER_HEADER = ("timestamp\titerations_used\tfinal_verdict\t"
                 "grounding_failures_first_pass\tnum_gaps\tid\n")


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def status_of(ws):
    f = ws / "status"
    if f.exists():
        return f.read_text(encoding="utf-8").strip().lower()
    # No declared status: a folder holding a resume was tailored; bare jd/parse = saved.
    if (ws / ".run" / "run.json").exists() or (ws / ".run" / "resume.json").exists():
        return "tailored"
    return "saved"


def posting_url_of(ws, pj):
    """Code-owned posting_url file, else a legacy parsed_jd.json field."""
    f = ws / ".run" / "posting_url"
    if f.exists():
        return f.read_text(encoding="utf-8").strip() or None
    return pj.get("posting_url")


def fmt_val(v):
    return "not stated" if v is None or v == "" else str(v)


def fmt_bool(v):
    return {True: "yes", False: "no", None: "not stated"}.get(v, "not stated")


def fmt_list(v):
    return ", ".join(v) if v else "not stated"


def cell(v):
    """A markdown table / TSV cell: never None, no raw pipes or tabs."""
    return ("" if v is None else str(v)).replace("|", "/").replace("\t", " ").strip()


def title_of(ws, pj):
    if pj.get("company") or pj.get("role_title"):
        return f"{fmt_val(pj.get('company'))} - {fmt_val(pj.get('role_title'))}"
    return ws.name  # the id is the label of last resort


def write_readme(ws, pj, rj):
    loc = pj.get("location") or {}
    where = ", ".join(x for x in (loc.get("city"), loc.get("state")) if x) or "not stated"
    lines = [
        f"# {title_of(ws, pj)}",
        "",
        f"- **id:** {ws.name}",
        f"- **Status:** {status_of(ws)}",
        f"- **Tailored:** {fmt_val(pj.get('date_parsed') or (rj.get('timestamp') or '')[:10])}",
        f"- **Verdict:** {fmt_val(rj.get('final_verdict'))} "
        f"({fmt_val(rj.get('iterations_used'))} fix cycle(s)); "
        f"grounding failures first pass: {fmt_val(rj.get('grounding_failures_first_pass'))}",
        f"- **Evidence gaps:** {fmt_val(rj.get('num_gaps'))} (see gaps.md)",
        f"- **Location:** {fmt_val(loc.get('mode'))}; {where}",
        f"- **Employment:** {fmt_val(pj.get('employment_type'))} "
        f"| sponsors H1B: {fmt_bool(pj.get('sponsors_h1b'))}",
        f"- **Salary (as posted):** {fmt_val(pj.get('salary_range'))}",
        f"- **Min years:** {fmt_val(pj.get('years_required_min'))}",
        f"- **Posting:** {fmt_val(posting_url_of(ws, pj))}",
        f"- **Required stack:** {fmt_list(pj.get('required_stack'))}",
        f"- **Preferred stack:** {fmt_list(pj.get('preferred_stack'))}",
        "",
    ]
    (ws / "README.md").write_text("\n".join(lines), encoding="utf-8")


def readme_stale(ws):
    m = ws / "README.md"
    if not m.exists():
        return True
    mt = m.stat().st_mtime
    return any((ws / n).exists() and (ws / n).stat().st_mtime > mt
               for n in (".run/run.json", ".run/parsed_jd.json", "status",
                         ".run/posting_url"))


def sanitize_part(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "")


def lift_pdf(ws, pj):
    """Copy .build/resume.pdf to the root as Resume_<Name>[_<Company>].pdf.

    The name comes from .build/applicant (render-time record; live profile only as
    fallback), so a later profile change never retro-renames a rendered resume."""
    src = ws / ".build" / "resume.pdf"
    if not src.exists():
        return
    marker = ws / ".build" / "applicant"
    applicant = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    if not applicant:
        applicant = load_json(BASE / "bank" / "profile.json").get("name") or ""
    name = sanitize_part(applicant)
    if not name:
        return
    company = sanitize_part(pj.get("company"))
    target = ws / (f"Resume_{name}_{company}.pdf" if company else f"Resume_{name}.pdf")
    for old in ws.glob("Resume_*.pdf"):
        if old != target:
            old.unlink()
    if not target.exists() or target.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, target)


def ensure_ledger_row(ws, rj):
    """Append this run's row unless it is already there (timestamp + id key)."""
    ts = rj.get("timestamp") or ""
    if not ts:
        return False
    if not LEDGER.exists():
        LEDGER.write_text(LEDGER_HEADER, encoding="utf-8")
    start, end = ts + "\t", "\t" + ws.name
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.startswith(start) and line.endswith(end):
            return False
    row = "\t".join(cell(v) for v in (
        ts, rj.get("iterations_used"),
        rj.get("final_verdict"), rj.get("grounding_failures_first_pass"),
        rj.get("num_gaps"), ws.name)) + "\n"
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(row)
    return True


def regenerate_index(workspaces):
    lines = ["# Applications", "",
             "| Date | Company | Role | Verdict | Gaps | Status | Folder |",
             "|---|---|---|---|---|---|---|"]
    for ws in sorted(workspaces, key=lambda w: w.name):
        pj = load_json(ws / ".run" / "parsed_jd.json")
        rj = load_json(ws / ".run" / "run.json")
        date = pj.get("date_parsed") or ws.name[:10]
        company = pj.get("company") or ws.name
        lines.append(
            f"| {cell(date)} | {cell(company)} | {cell(pj.get('role_title'))} "
            f"| {cell(rj.get('final_verdict'))} | {cell(rj.get('num_gaps'))} "
            f"| {cell(status_of(ws))} | [{ws.name}]({ws.name}/) |")
    INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if not APPS.is_dir():
        print("finalize.py: no applications/ directory; nothing to finalize.")
        return 0
    marked = [d for d in APPS.iterdir() if d.is_dir() and (d / "jd.txt").exists()]
    if len(sys.argv) > 1:
        target = Path(sys.argv[1]).resolve()
        todo = [w for w in marked if w.resolve() == target]
        if not todo:
            print(f"finalize.py: {sys.argv[1]} is not a marked workspace; nothing to do.")
            return 0
    else:
        todo = marked

    new_rows = 0
    for ws in todo:
        pj = load_json(ws / ".run" / "parsed_jd.json")
        lift_pdf(ws, pj)  # a rendered PDF ships named even when run.json never landed
        rj = load_json(ws / ".run" / "run.json")
        if not rj:
            continue  # never ran (a saved application); the index below still lists it
        if readme_stale(ws):
            write_readme(ws, pj, rj)
        if ensure_ledger_row(ws, rj):
            new_rows += 1
    regenerate_index(marked)
    print(f"finalize.py: swept {len(todo)} workspace(s); {new_rows} new ledger row(s); "
          f"index regenerated ({len(marked)} listed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
