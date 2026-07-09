#!/usr/bin/env python3
"""Keyword gate: the JD's keywords, on the resume in the JD's spelling, or in gaps.md.

ATS systems exact-match strings ("Go" vs "Golang"), so code owns presence and spelling;
the drafter owns honesty, the evaluator's grounding gate owns whether a present term is
backed. For each JD term with bank support (word-boundary match plus a small
same-referent alias table), at most one "- " line, which check.sh blocks on:
  - missing (bank-supported): <term>       not on the resume, no variant in gaps.md
  - spelling differs from JD: ...          a variant is on the resume, the JD's form is not
Recording a term in gaps.md dismisses it (a bank grep hit is not always honest support).

usage : keyword_check.py <workspace>
Prints "None." when clean. Always exits 0; check.sh owns blocking and retry caps.
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BANK = BASE / "bank" / "experience_bank.md"

# Admission rule: same referent in any context (renamings, abbreviations, spellings);
# concept merges (gui/user-interface) are the drafter's adjacency judgment, never here.
ALIAS_GROUPS = [
    {"go", "golang"},
    {"postgresql", "postgres"},
    {"kubernetes", "k8s"},
    {"javascript", "js"},
    {"typescript", "ts"},
    {"aws", "amazon web services"},
    {"gcp", "google cloud", "google cloud platform"},
    {"ci/cd", "ci-cd", "cicd"},
    {"node.js", "nodejs"},
    {"react", "react.js", "reactjs"},
    {"next.js", "nextjs"},
    {"machine learning", "ml"},
]
ALIASES = {v: g for g in ALIAS_GROUPS for v in g}


def pattern(term):
    # Word boundaries that survive tech names: "go" never matches "golang" or
    # "Django"; "c" never matches "c++" or "c#"; "js" never matches "node.js".
    return re.compile(
        r"(?<![A-Za-z0-9+#.])" + re.escape(term) + r"(?![A-Za-z0-9+#])",
        re.IGNORECASE,
    )


def main():
    if len(sys.argv) != 2:
        print("usage: keyword_check.py <workspace>", file=sys.stderr)
        return 0
    ws = Path(sys.argv[1])

    try:
        parsed = json.loads((ws / ".run" / "parsed_jd.json").read_text())
    except (OSError, ValueError):
        print("No readable parsed_jd.json; keyword check skipped.")
        return 0
    try:
        resume_text = (ws / ".run" / "resume.json").read_text()
    except OSError:
        print("No resume.json yet; keyword check skipped.")
        return 0
    try:
        bank_text = BANK.read_text()
    except OSError:
        print("No experience bank found; keyword check skipped.")
        return 0
    try:
        gaps_text = (ws / "gaps.md").read_text()
    except OSError:
        gaps_text = ""

    # keywords is the primary list; the stack fields fill in for older workspaces.
    terms = []  # (term as the JD spells it, preferred?)
    seen = set()
    for field, preferred in (("keywords", False), ("required_stack", False),
                             ("preferred_stack", True)):
        for term in parsed.get(field) or []:
            key = term.strip().casefold()
            if key and key not in seen:
                seen.add(key)
                terms.append((term.strip(), preferred))
    if not terms:
        print("parsed_jd.json lists no keywords; keyword check skipped.")
        return 0

    missing, spelling = [], []
    for term, preferred in terms:
        variants = ALIASES.get(term.casefold(), {term.casefold()})
        if not any(pattern(v).search(bank_text) for v in variants):
            continue  # no bank support: an honest gap is the drafter's Step A, not a gate
        if pattern(term).search(resume_text):
            continue  # present in the JD's own spelling
        variant_hit = None
        for v in variants:
            if v != term.casefold():
                m = pattern(v).search(resume_text)
                if m:
                    variant_hit = m.group(0)
                    break
        if variant_hit:
            spelling.append(
                f'- spelling differs from JD: resume has "{variant_hit}", JD says "{term}"')
        elif not any(pattern(v).search(gaps_text) for v in variants):
            tag = ", preferred" if preferred else ""
            missing.append(f"- missing (bank-supported{tag}): {term}")

    lines = missing + spelling
    print("\n".join(lines) if lines else "None.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
