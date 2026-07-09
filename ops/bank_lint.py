#!/usr/bin/env python3
"""Bank integrity checks against spec/bank_format.md (the code-checkable half).

Checks profile.json and experience_bank.md against the contract and each other:
structure, round-trip (Role IDs and titles match both ways, profile.json wins), and
dates. Prints one finding per line: 'ERROR:' (fix before use) or 'WARN:' (known gap).

usage : bank_lint.py <bank_dir>
exit  : 0 clean / 1 warnings only / 2 errors / 3 usage or unreadable input
"""
import json
import re
import sys
from pathlib import Path

REQUIRED_HEADER_FIELDS = ("Role ID", "Acceptable titles", "Dates", "Location")
HEADER_FIELD_NAMES = set(REQUIRED_HEADER_FIELDS) | {"Type"}

MONTHS = {"January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
          "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
          "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec"}


def norm_dates(s):
    """Abbreviate month names so 'December 2025' and 'Dec 2025' compare equal."""
    for full, abbr in MONTHS.items():
        s = s.replace(full, abbr)
    return s


def parse_profile(path, findings):
    try:
        profile = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        findings.append(("ERROR", f"profile.json unreadable or invalid JSON: {e}"))
        return None
    if not profile.get("name"):
        findings.append(("WARN", "profile.json: 'name' is missing or empty"))
    if not isinstance(profile.get("contact"), dict):
        findings.append(("ERROR", "profile.json: 'contact' must be an object"))
    roles = profile.get("roles")
    if not isinstance(roles, list) or not roles:
        findings.append(("ERROR", "profile.json: 'roles' must be a non-empty list"))
        return profile
    seen = set()
    for i, r in enumerate(roles):
        rid = r.get("id")
        if not rid:
            findings.append(("ERROR", f"profile.json: roles[{i}] has no 'id'"))
            continue
        if rid in seen:
            findings.append(("ERROR", f"profile.json: duplicate role id '{rid}'"))
        seen.add(rid)
        if not r.get("employer"):
            findings.append(("ERROR", f"profile.json: role '{rid}' has no employer"))
        if not r.get("title"):
            findings.append(("ERROR", f"profile.json: role '{rid}' has no title"))
        for field in ("start", "end"):
            if r.get(field) is None:
                findings.append(("WARN",
                    f"profile.json: role '{rid}' has null '{field}' (unresolved record field)"))
    for i, e in enumerate(profile.get("education", [])):
        for field in ("institution", "degree"):
            if not e.get(field):
                findings.append(("ERROR", f"profile.json: education[{i}] has no '{field}'"))
    return profile


def parse_bank_roles(text):
    """Return [{id, titles_line, fields, body}] for each role under ## Work Experience."""
    m = re.search(r"^## Work Experience\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return None
    roles = []
    for section in re.split(r"^### ", m.group(1), flags=re.M)[1:]:
        fields = dict(re.findall(r"^\*\*([^*:]+):\*\* *(.*)$", section, re.M))
        roles.append({
            "heading": section.splitlines()[0].strip(),
            "fields": fields,
            "body": section,
        })
    return roles


def check_bank(bank_text, profile, findings):
    roles = parse_bank_roles(bank_text)
    if roles is None:
        findings.append(("ERROR", "experience_bank.md: no '## Work Experience' section"))
        return
    if not roles:
        findings.append(("ERROR", "experience_bank.md: no role entries under Work Experience"))
        return

    prof_roles = {r["id"]: r for r in (profile or {}).get("roles", []) if r.get("id")}
    seen_ids = set()

    for role in roles:
        head = role["heading"]
        fields = role["fields"]
        for f in REQUIRED_HEADER_FIELDS:
            if f not in fields or not fields[f].strip():
                findings.append(("ERROR", f"bank role '{head}': header missing '**{f}:**'"))
        rid = fields.get("Role ID", "").strip()
        if not rid:
            continue
        if rid in seen_ids:
            findings.append(("ERROR", f"bank role id '{rid}' appears more than once"))
        seen_ids.add(rid)

        # units: contribution headings, or a flat body with at least one evidence section
        # (any bold label beyond the header fields: '**What was built**', '**Phase 1: ...**')
        units = re.findall(r"^#### +(.+)$", role["body"], re.M)
        evidence_labels = [lbl for lbl in re.findall(r"^\*\*([^*]+?):?\*\*", role["body"], re.M)
                           if lbl.split(":")[0] not in HEADER_FIELD_NAMES]
        if not units and not evidence_labels:
            findings.append(("ERROR",
                f"bank role '{rid}': no units (no '#### ' contribution and no evidence sections)"))
        for unit_body in re.split(r"^#### ", role["body"], flags=re.M)[1:]:
            title = unit_body.splitlines()[0].strip()
            if not re.search(r"^\*\*(What it is|What was built)\*\*", unit_body, re.M):
                findings.append(("ERROR",
                    f"bank role '{rid}', unit '{title}': no '**What it is**' / '**What was built**' field"))
            if not re.search(r"^\*\*Stack\*\*", unit_body, re.M):
                findings.append(("WARN",
                    f"bank role '{rid}', unit '{title}': no '**Stack**' field (fine for an analysis/decision unit)"))

        # round-trip with profile.json
        if rid not in prof_roles:
            findings.append(("ERROR", f"bank role id '{rid}' not found in profile.json"))
            continue
        pr = prof_roles[rid]
        expected = [pr["title"]] + list(pr.get("title_variants", []))
        actual = [t.strip() for t in fields.get("Acceptable titles", "").split("|") if t.strip()]
        if actual != expected:
            findings.append(("ERROR",
                f"bank role '{rid}': Acceptable titles {actual} != profile title+variants {expected}"))
        dates_line = norm_dates(fields.get("Dates", ""))
        for field in ("start", "end"):
            val = pr.get(field)
            if val is None:
                findings.append(("WARN",
                    f"bank role '{rid}': profile '{field}' is null; Dates line is '{dates_line}'"))
            elif norm_dates(val) not in dates_line:
                findings.append(("ERROR",
                    f"bank role '{rid}': Dates line '{dates_line}' does not contain profile {field} '{val}'"))

    for rid in prof_roles:
        if rid not in seen_ids:
            findings.append(("ERROR", f"profile.json role '{rid}' has no entry in experience_bank.md"))


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 3
    bank = Path(argv[1])
    bank_md = bank / "experience_bank.md"
    profile_path = bank / "profile.json"
    for p in (bank_md, profile_path):
        if not p.is_file():
            print(f"bank_lint: missing {p}", file=sys.stderr)
            return 3

    findings = []
    profile = parse_profile(profile_path, findings)
    check_bank(bank_md.read_text(), profile, findings)

    for level, msg in findings:
        print(f"{level}: {msg}")
    errors = sum(1 for level, _ in findings if level == "ERROR")
    warns = len(findings) - errors
    print(f"bank_lint: {errors} error(s), {warns} warning(s)")
    return 2 if errors else (1 if warns else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
