#!/usr/bin/env python3
"""Ingest raw career sources: copy into <bank>/sources/, extract text, write the manifest.

sources/ is append-only provenance: files are added (duplicates skipped, name
collisions suffixed), never edited. Text extraction: pdf via `pdftotext -layout`
(too little text or no extractor falls back to the stored PDF); md/txt/tex read in
place. Every source lands in <bank>/.ingest/manifest.json, which the extract stage
works from; each run is appended to <bank>/log.md.

usage : bank_ingest.py <bank_dir> [file ...]   (no files: ingest sources/ as-is)
exit  : 0 at least one ingested / 2 usage / 4 nothing ingested
"""
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

MIN_CHARS = 200  # under this, a PDF extraction is a scan or a garble, not a resume

TEXT_SUFFIXES = {".md", ".txt", ".tex"}


def store_source(src: Path, sources: Path):
    """Copy src into sources/ immutably. Returns (stored_path, duplicate: bool)."""
    sources.mkdir(parents=True, exist_ok=True)
    if src.parent.resolve() == sources.resolve():
        return src, False  # already in the drop box; use in place
    data = src.read_bytes()
    dest = sources / src.name
    n = 2
    while dest.exists():
        if dest.read_bytes() == data:
            return dest, True
        dest = sources / f"{src.stem}-{n}{src.suffix}"
        n += 1
    dest.write_bytes(data)
    return dest, False


def extract_pdf(stored: Path, workdir: Path):
    """pdftotext -layout -> (text_path, chars, status)."""
    if not shutil.which("pdftotext"):
        return None, 0, "no_extractor"
    out = workdir / f"{stored.stem}.txt"
    r = subprocess.run(["pdftotext", "-layout", str(stored), str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        return None, 0, "extract_failed"
    chars = len(out.read_text(errors="replace").strip())
    return out, chars, ("ok" if chars >= MIN_CHARS else "low_yield")


def read_as_text(stored: Path):
    """Text formats are their own extraction. Returns (chars, ok: bool)."""
    try:
        return len(stored.read_text(encoding="utf-8").strip()), True
    except (UnicodeDecodeError, OSError):
        return 0, False


def ingest_one(src: Path, sources: Path, workdir: Path):
    """Returns a manifest entry dict; status field says how it went."""
    entry = {"source": src.name, "format": src.suffix.lstrip(".").lower() or "unknown"}
    if not src.is_file():
        entry.update(status="missing", stored=None, text_path=None,
                     extraction=None, chars=0)
        return entry

    stored, duplicate = store_source(src, sources)
    entry["stored"] = str(stored)
    entry["duplicate"] = duplicate

    if src.suffix.lower() == ".pdf":
        text_path, chars, status = extract_pdf(stored, workdir)
        entry.update(extraction="pdftotext-layout" if text_path else None,
                     text_path=str(text_path) if text_path else str(stored),
                     chars=chars, status=status)
    else:
        chars, ok = read_as_text(stored)
        if not ok:
            status = "not_text"
        elif not chars:
            status = "empty"
        elif chars < MIN_CHARS:
            status = "low_yield"
        else:
            status = "ok"
        entry.update(extraction="text", text_path=str(stored), chars=chars, status=status)
    return entry


def append_log(bank: Path, entries):
    names = ", ".join(e["source"] for e in entries)
    today = datetime.date.today().isoformat()
    lines = [f"## [{today}] ingest | {names}"]
    for e in entries:
        detail = f"{e['format']}, {e['chars']} chars, {e['status']}"
        if e.get("duplicate"):
            detail += ", duplicate of existing source"
        lines.append(f"- {e['source']}: {detail}")
    log = bank / "log.md"
    prefix = "" if not log.exists() else log.read_text() + "\n"
    if not prefix:
        prefix = "# Bank log\n*Append-only journal of bank operations.*\n\n"
    log.write_text(prefix + "\n".join(lines) + "\n")


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    bank = Path(argv[1])
    if not bank.is_dir():
        print(f"bank_ingest: not a directory: {bank}", file=sys.stderr)
        return 2

    sources = bank / "sources"
    workdir = bank / ".ingest"
    workdir.mkdir(parents=True, exist_ok=True)

    if len(argv) > 2:
        inputs = [Path(a) for a in argv[2:]]
    else:  # drop-box flow: ingest whatever the user put in sources/
        inputs = sorted(p for p in sources.iterdir() if p.is_file()) if sources.is_dir() else []
        if not inputs:
            print(f"bank_ingest: nothing to ingest; drop files into {sources}/", file=sys.stderr)
            return 4

    entries = [ingest_one(p, sources, workdir) for p in inputs]
    (workdir / "manifest.json").write_text(json.dumps(entries, indent=2) + "\n")
    append_log(bank, entries)

    ok_statuses = ("ok", "low_yield", "no_extractor")
    ok = [e for e in entries if e["status"] in ok_statuses]
    for e in entries:
        if e["status"] not in ok_statuses:
            print(f"bank_ingest: {e['source']}: {e['status']}", file=sys.stderr)
    print(json.dumps({"ingested": len(ok), "failed": len(entries) - len(ok),
                      "manifest": str(workdir / "manifest.json")}))
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main(sys.argv))
