#!/usr/bin/env python3
"""Render <ws>/.run/resume.json + bank/profile.json into <ws>/.run/resume.tex.

The model writes JSON content only; the record layer (employers, titles, dates,
education) comes from profile.json and all LaTeX escaping happens here, so the model
cannot break rendering or alter record facts.

This engine owns the schema walk and the escaping policy; a template is one
declarative module (ops/templates/<name>.py) contributing a SKELETON (layout) and
FRAGMENTS (markup), and never touches content.

usage : render.py <workspace>
exit  : 0 ok / 2 invalid input (message fed back to the writer by the hook)
"""
import json
import os
import re
import sys
from pathlib import Path

from templates import jake

BASE = Path(__file__).resolve().parent.parent
PROFILE = BASE / "bank" / "profile.json"
DEFAULT_TEMPLATE = "jake"


class RenderError(Exception):
    pass


# Refuse folders without the jd.txt marker so a mistyped path cannot be rendered into.
def workspace():
    if len(sys.argv) < 2:
        raise RenderError("usage: render.py <workspace>  (a folder holding "
                          ".run/resume.json, e.g. applications/<id>)")
    ws = Path(sys.argv[1]).resolve()
    if not (ws / "jd.txt").exists():
        raise RenderError(f"{ws} is not an initialized workspace (no jd.txt marker); "
                          "workspaces are created by ops/new_workspace.py via /tailor.")
    return ws

MAX_BULLET_WORDS = int(os.environ.get("RESUME_MAX_BULLET_WORDS", "50"))

# --- LaTeX escaping (single pass, no double-escaping) ----------------------
_ESC = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}
_ESC_RE = re.compile("|".join(re.escape(k) for k in sorted(_ESC, key=len, reverse=True)))


# --- character normalization (model-authored content only, before escaping) --
_NORMALIZE = [
    (re.compile(r"\s*—\s*"), ", "),              # em-dash; scan_lints also flags it for rewrite
    (re.compile(r"–"), "--"),                    # en-dash -> LaTeX-safe ASCII
    (re.compile(r"~(?=\d)"), "approximately "),  # "~5" -> "approximately 5"
    (re.compile(r"~"), ""),                      # stray "~" dropped
]


def normalize(s):
    s = "" if s is None else str(s)
    for pat, repl in _NORMALIZE:
        s = pat.sub(repl, s)
    return s


def esc(s):
    """Escape a record-layer value (profile.json): escape only, never normalized."""
    return _ESC_RE.sub(lambda m: _ESC[m.group()], "" if s is None else str(s))


def esc_content(s):
    """Escape a model-authored value: normalize, then escape. Never the record layer."""
    return _ESC_RE.sub(lambda m: _ESC[m.group()], normalize(s))


# --- validation ------------------------------------------------------------
def require(cond, msg):
    if not cond:
        raise RenderError(msg)


def validate(resume, roles_by_id):
    require(isinstance(resume, dict), "resume.json must be a JSON object")

    skills = resume.get("skills", [])
    require(isinstance(skills, list), "'skills' must be a list")
    for i, c in enumerate(skills):
        require(isinstance(c, dict) and "category" in c and "items" in c,
                f"skills[{i}] needs 'category' and 'items'")
        require(isinstance(c["items"], list) and c["items"],
                f"skills[{i}].items must be a non-empty list")

    exp = resume.get("experience", [])
    require(isinstance(exp, list) and exp, "'experience' must be a non-empty list")
    for i, e in enumerate(exp):
        require(isinstance(e, dict), f"experience[{i}] must be an object")
        rid = e.get("role_id")
        require(rid in roles_by_id,
                f"experience[{i}].role_id '{rid}' not found in profile.json roles")
        role = roles_by_id[rid]
        allowed = {role["title"], *role.get("title_variants", [])}
        tc = e.get("title_choice", role["title"])
        require(tc in allowed,
                f"experience[{i}].title_choice '{tc}' is not the canonical title "
                f"or a vetted variant for role '{rid}'. Allowed: {sorted(allowed)}")
        require(isinstance(e.get("bullets"), list) and e["bullets"],
                f"experience[{i}].bullets must be a non-empty list")

    for i, p in enumerate(resume.get("projects", []) or []):
        require(isinstance(p, dict) and p.get("name") and isinstance(p.get("bullets"), list),
                f"projects[{i}] needs 'name' and a 'bullets' list")


# --- engine: schema walk; the template's fragments supply all markup ---------
def fill(F, key, **vals):
    return F[key] % vals


def build_contact(F, profile):
    c = profile.get("contact", {})
    parts = []
    if c.get("phone"):
        parts.append(fill(F, "contact.text", text=esc(c["phone"])))
    if c.get("email"):
        parts.append(fill(F, "contact.email", url=c["email"], text=esc(c["email"])))
    for link in c.get("links", []):
        parts.append(fill(F, "contact.link", url=link["url"], text=esc(link["label"])))
    if c.get("base_location"):
        parts.append(fill(F, "contact.text", text=esc(c["base_location"])))
    return F["contact.sep"].join(parts)


def build_skills(F, resume):
    rows = F["skills.row_sep"].join(
        fill(F, "skills.row",
             category=esc_content(c["category"]),
             items=F["skills.item_sep"].join(esc_content(x) for x in c["items"]))
        for c in resume["skills"])
    return fill(F, "skills.section", rows=rows)


def build_experience(F, resume, roles_by_id):
    entries = []
    for e in resume["experience"]:
        role = roles_by_id[e["role_id"]]
        bullets = "\n".join(fill(F, "experience.bullet", text=esc_content(b))
                            for b in e["bullets"])
        entries.append(fill(
            F, "experience.entry",
            title=esc(e.get("title_choice", role["title"])),
            dates=fill(F, "dates.range", start=esc(role["start"]), end=esc(role["end"])),
            employer=esc(role["employer"]),
            location=esc(role.get("location", "")),
            bullets=bullets))
    return fill(F, "experience.section", entries="\n".join(entries))


def build_projects(F, resume):
    projects = resume.get("projects") or []
    if not projects:
        return ""
    entries = []
    for p in projects:
        head = fill(F, "projects.head", name=esc_content(p["name"]))
        if p.get("stack"):
            head += fill(F, "projects.stack", stack=esc_content(p["stack"]))
        bullets = "\n".join(fill(F, "projects.bullet", text=esc_content(b))
                            for b in p["bullets"])
        entries.append(fill(F, "projects.entry", head=head,
                            dates=esc_content(p.get("dates", "")), bullets=bullets))
    return fill(F, "projects.section", entries="\n".join(entries))


def build_education(F, profile, resume):
    edu = profile.get("education", [])
    if not edu:
        return ""
    entries = "\n".join(fill(
        F, "education.entry",
        degree=esc(ed["degree"]),
        dates=fill(F, "dates.range", start=esc(ed["start"]), end=esc(ed["end"])),
        institution=esc(ed["institution"]),
        location=esc(ed.get("location", "")))
        for ed in edu)
    coursework = resume.get("relevant_coursework") or []
    block = (fill(F, "education.coursework", items=esc_content(", ".join(coursework)))
             if coursework else "")
    return fill(F, "education.section", entries=entries, coursework=block)


def build_slots(F, profile, resume, roles_by_id):
    return {
        "%%NAME%%": esc(profile.get("name", "")),
        "%%CONTACT%%": build_contact(F, profile),
        "%%SKILLS%%": build_skills(F, resume),
        "%%EXPERIENCE%%": build_experience(F, resume, roles_by_id),
        "%%PROJECTS%%": build_projects(F, resume),
        "%%EDUCATION%%": build_education(F, profile, resume),
    }


# --- template registry --------------------------------------------------------
# A template is one module in ops/templates/ exposing SKELETON and FRAGMENTS.
TEMPLATES = {"jake": jake}


# --- craft lints (flagged, never blocked here; check.sh owns blocking) -------
def scan_lints(resume):
    """Scan every bullet list; returns (over_length, repeated_openers, em_dashes)."""
    long_flags, verb_flags, em_flags = [], [], []

    def opener(b):
        toks = str(b).split()
        return toks[0].strip(".,;:()").lower() if toks else ""

    def scan(label, bullets):
        bullets = bullets or []
        for i, b in enumerate(bullets):
            n = len(str(b).split())
            if n > MAX_BULLET_WORDS:
                long_flags.append((f"{label} bullet {i}", n, b))
            if "—" in str(b):
                em_flags.append((f"{label} bullet {i}", b))
        seen = {}
        for i, b in enumerate(bullets):
            seen.setdefault(opener(b), []).append(i)
        for word, idxs in seen.items():
            if word and len(idxs) > 1:
                verb_flags.append((label, word, idxs))

    for e in resume.get("experience", []) or []:
        scan(f"experience '{e.get('role_id', '?')}'", e.get("bullets"))
    for p in resume.get("projects", []) or []:
        scan(f"project '{p.get('name', '?')}'", p.get("bullets"))
    return long_flags, verb_flags, em_flags


def write_lint_flags(resume, lint_flags_path):
    """Write scan_lints findings to lint_flags.md; returns the same three lists."""
    long_flags, verb_flags, em_flags = scan_lints(resume)

    out = [f"# Lint flags (length cap: {MAX_BULLET_WORDS} words/bullet)", "",
           "## Over-length bullets"]
    if long_flags:
        out.append(f"Tighten each to under {MAX_BULLET_WORDS} words, grounded (cut "
                   f"re-listed stack/implementation detail, not the outcome):")
        out += [f"- **{loc}** ({n} words): {text}" for loc, n, text in long_flags]
    else:
        out.append(f"None; all within {MAX_BULLET_WORDS} words.")
    out += ["", "## Repeated opening words (same role/project)"]
    if verb_flags:
        out.append("Vary the lead verb so no two bullets in a role open the same way:")
        out += [f"- **{label}**: {len(idxs)} bullets open with \"{word}\" "
                f"(bullets {', '.join(map(str, idxs))})"
                for label, word, idxs in verb_flags]
    else:
        out.append("None; openers vary within each role.")
    out += ["", "## Em-dashes (AI tell; rewrite, do not just swap punctuation)"]
    if em_flags:
        out.append("Remove each em-dash by rewriting the line: commas for an aside, a "
                   "semicolon or two sentences for linked independent clauses; best, "
                   "recast so the dash is unneeded. (render.py renders a comma as a "
                   "fallback, but fix it at the source in resume.json.)")
        out += [f"- **{loc}**: {text}" for loc, text in em_flags]
    else:
        out.append("None.")
    lint_flags_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return long_flags, verb_flags, em_flags


# --- main ------------------------------------------------------------------
def load_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RenderError(f"{what} not found at {path}")
    except json.JSONDecodeError as ex:
        raise RenderError(f"{what} is not valid JSON: {ex}")


def main():
    ws = workspace()
    resume_path = ws / ".run" / "resume.json"
    out_path = ws / ".run" / "resume.tex"
    build = ws / ".build"
    build.mkdir(parents=True, exist_ok=True)
    lint_flags_path = build / "lint_flags.md"

    profile = load_json(PROFILE, "profile.json")
    resume = load_json(resume_path, "resume.json")
    roles_by_id = {r["id"]: r for r in profile.get("roles", [])}

    validate(resume, roles_by_id)
    long_flags, verb_flags, em_flags = write_lint_flags(resume, lint_flags_path)

    template = TEMPLATES[DEFAULT_TEMPLATE]
    tex = template.SKELETON
    slots = build_slots(template.FRAGMENTS, profile, resume, roles_by_id)
    missing = [k for k in slots if k not in tex]
    if missing:
        raise RenderError(f"template '{DEFAULT_TEMPLATE}' is missing slots: {missing}")
    for k, v in slots.items():
        tex = tex.replace(k, v)

    out_path.write_text(tex, encoding="utf-8")
    # Name-at-render-time record; finalize.py names the shipped PDF from it, so a
    # later profile change never retro-renames a rendered resume.
    (build / "applicant").write_text(profile.get("name", "") + "\n", encoding="utf-8")
    note = f"render.py: wrote {out_path}"
    n = len(long_flags) + len(verb_flags) + len(em_flags)
    if n:
        note += f" ({n} lint flag(s); see {lint_flags_path})"
    print(note)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RenderError as ex:
        sys.stderr.write("BLOCK: render.py rejected the write.\n%s\n" % ex)
        sys.exit(2)
