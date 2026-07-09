# Bank format contract

The canonical structure of `bank/experience_bank.md` and `bank/profile.json`. Anything that
writes the bank (onboarding's extract stage, `/bank-add`, a hand edit) writes to this shape;
anything that checks it (`bank-lint`) checks against it; anything that reads it (`/bank-map`,
the tailoring agents) may rely on it. One contract, so independently produced banks all work
with the same product code.

The contract is strict exactly where a consumer depends on the structure, and free where
the work itself varies. Two rules run through everything:

- **Facts only.** The bank records what happened: systems, decisions, numbers, tools,
  outcomes. Numbers appear verbatim as the user stated them. A fact nobody provided is not
  written; a gap stays a gap.
- **Grep-visible evidence.** The tailoring evaluator grounds resume claims by searching this
  file. A tool, metric, or outcome that supports a resume claim must appear here in plain
  text, by its real name, not summarized away.

## The two files

- **`experience_bank.md`**, the evidence layer: what the work was and why it mattered.
  Agents read it; it is the only source of facts for resume claims.
- **`profile.json`**, the record layer: name, contact, employers, titles + variants, dates,
  education. Only `ops/render.py` reads it; agents never do. It is canonical for everything it
  holds; where the two files state the same fact, `profile.json` wins.

## `profile.json`

```json
{
  "name": "Full Name",
  "contact": { "location": "...", "email": "...", "phone": "...", "linkedin": "...", "github": "..." },
  "roles": [
    {
      "id": "acme-de",
      "employer": "Acme Corp",
      "location": "City, ST",
      "start": "Month YYYY",
      "end": "Month YYYY",
      "title": "Data Engineer",
      "title_variants": ["Data Platform Engineer", "Software Engineer"]
    }
  ],
  "education": [
    { "id": "state-u", "institution": "State University", "location": "City, ST",
      "degree": "B.S. in Computer Science", "start": "Month YYYY", "end": "Month YYYY",
      "gpa": "3.8", "honors": "magna cum laude" }
  ],
  "application": {
    "work_authorization": "US citizen / permanent resident / visa status as stated",
    "needs_sponsorship": false,
    "salary_expectation": "as stated by the user",
    "notice_period": "2 weeks",
    "relocation": "as stated",
    "work_preference": "remote | hybrid | onsite"
  },
  "self_id": {
    "gender": "...", "ethnicity": "...", "veteran_status": "...", "disability_status": "..."
  }
}
```

- `education[].gpa` and `education[].honors` are optional record facts, stated verbatim.
- **`application`** (optional, and every key inside it optional) holds application-form
  data: never rendered on the resume, never read by the tailoring agents; it exists so
  form-filling never has to re-ask. Values are the user's words, recorded, not inferred.
- **`self_id`** (optional) holds voluntary EEO self-identification. Stored ONLY if the
  user volunteers it, never asked as a requirement, never read by tailoring, never
  rendered. Omit the block entirely when nothing was volunteered.
- `ops/render.py` reads only the fields it renders and ignores unknown keys, so these blocks
  are free to be absent or present.

- `roles[].id` is the **Role ID**: a short kebab-case slug, unique, stable once minted
  (resume.json references it; renaming breaks every workspace that used it). Mint as
  employer-slug plus a discriminator when one employer has several roles (`acme-de`,
  `acme-intern`).
- `title` is the canonical title; `title_variants` are honest alternatives the user actually
  held or that truthfully describe the role. Together they are the complete `title_choice`
  allowlist; a title not listed here cannot appear on a resume.

## `experience_bank.md`: document skeleton

Top-level sections, in order, all `##` headings:

1. `## Profile`: name, location, contact, target roles, availability, as `**Label:** value`
   lines. Informational for agents; `profile.json` stays canonical for the record fields.
2. `## Work Experience`: one role entry per `profile.json` role (see below).
3. `## Projects`: standalone project units (see below).
4. `## Education`: degree, institution, dates, relevant coursework, GPA/honors if the
   user states them. Canonical in `profile.json`; coursework lives only here.
5. `## Technical Skills`: `**Category**` label followed by a `·`-separated item line.
   Every tool named in a role or project unit should also appear in a category here.

Optional sections, present only when the user has the material, placed after Education:

- `## Certifications`: one `- ` line per credential: name, issuer, year, verbatim
  (`- AWS Solutions Architect – Associate, Amazon Web Services, 2023`). Credentials are
  record-layer claims: zero degrees of freedom, never paraphrased.
- `## Awards`, `## Publications`, `## Languages` (human languages): same one-line-per-item
  shape, facts verbatim.

A leading document title and table of contents are optional. `---` rules between entries are
convention, not contract.

## Role entry

Header block: every field required, every role, except `Type`, which appears only when a
source or the user states the employment type (an unstated type is unknown, not "Full-time"):

```markdown
### Acme Corp, Data Engineer (Full-Time)
**Role ID:** acme-de
**Acceptable titles:** Data Engineer | Data Platform Engineer | Software Engineer
**Dates:** Month YYYY – Month YYYY
**Location:** City, ST
**Type:** Full-time
```

followed by a one-or-two-sentence plain-text summary of what the role owns.

**Round-trip invariant (the one lint checks hardest):** `Role ID` matches a `profile.json`
`roles[].id`; `Acceptable titles` is exactly that role's `title` (listed first, it is the
canonical title) followed by its `title_variants`, `|`-separated; `Dates` and `Location`
match the profile values. Every profile role has a bank entry and vice versa. If they ever
disagree, `profile.json` wins and the render rejects the stale choice.

## Units: the evidence itself

A **unit** is one coherent piece of true work: a system owned, a project shipped, a
measurable initiative, a design decision with consequences.

**Admission bar.** Too fine is not a unit: a bug fixed, a config tweaked, a routine task;
at most those are evidence lines *inside* a unit's narrative. Too coarse is not a unit
either: a whole role is a container of units, never one unit. When in doubt, ask whether
the piece could carry a resume bullet on its own; if not, it merges upward or stays out.

Units take one of two shapes, by the richness of the role:

**Contribution units**: for a role with several distinct ownable pieces. Each is a `####`
heading under the role:

```markdown
#### Contribution 1: Payments Reconciliation Platform (Headline Contribution)

**What it is**
One paragraph: the system, what it does, where it sits.

**Role:** Sole designer and builder of the matching engine and its API.

**Design contributions**

*Matching-engine data model*
What was decided and why, as prose. Real decisions with the options weighed and the
reasoning, at whatever depth the user actually provided.

**Stack**
PostgreSQL · Python · FastAPI · Docker

**Status**
Deployed; adopted by two downstream teams.
```

**Flat role body**: for a lighter role that is essentially one story:

```markdown
**What was built**
- One bolded-lead bullet per piece of work, each carrying its own facts and tool names
- ...

**Stack**
React · TypeScript · GraphQL
```

### Unit fields

Required in every unit (contribution or flat):

- **What it is** (contribution) / **What was built** (flat): the work, concretely.
- **Stack**: the real tools, `·`-separated, by their real names.

Standard optional fields, used when true material exists for them:

- **Role:** the user's actual ownership (sole builder, led, contributed).
- **Design contributions**: the decision layer (options weighed, tradeoffs, reasoning).
  This is the field that lets tailoring surface honest adjacent experience later; it is
  the single most valuable thing onboarding can recover.
- **Status**: deployed / adopted / POC / shipped-to-N-users.
- **Results**: measurable outcomes, numbers verbatim.
- **Scale**: users, data volume, team size, duration.

Beyond these, evidence sections are **free**: a bolded label followed by facts, shaped to
the work's own structure (`**Phase 1: Hardware exploration**`, `**Architecture decisions**`,
`**Technical problems solved**`). The contract fixes the required core and the two
document-level rules (facts only, grep-visible); it does not force every story into one mold.

## Project entry

Under `## Projects`, same unit discipline, standalone:

```markdown
### ProjectName: one-line descriptor

**What it is**
...

**What was built**
- ...

**Results**
Numbers verbatim, if any exist.

**Stack**
...
```

Project names must be real; a resume's projects section traces here by name.

## What consumers rely on (why the strict parts are strict)

- **`ops/render.py`** never reads this file; the record layer comes from `profile.json`. That
  is why the round-trip invariant matters: the bank's headers are the agents' only view of
  the record, and they must not drift from what ops/render.py will enforce.
- **The tailoring evaluator** greps this file to ground every resume claim; the
  grep-visible rule exists for it.
- **The drafter** reads role headers for Role IDs and title allowlists, and unit bodies for
  facts to select and frame.
- **`/bank-map`** derives `evidence_map.md` from the unit structure: one angle-inventory
  entry per unit, requirement lookups keyed by the facts in unit bodies.
