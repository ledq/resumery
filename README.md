# resumery

[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Runs in Claude Code](https://img.shields.io/badge/runs%20in-Claude%20Code-D97757)](https://claude.com/claude-code)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)

Turn your career history into a structured evidence bank, then tailor a truthful one-page resume to any job posting. Runs inside Claude Code.

## What it is
 
resumery has two parts:
 
1. **The bank.** A persistent, structured record of your career: every role, project, and design decision, with provenance. You build it once from your existing resumes and grow it over time. Because it holds more than any single resume does, tailoring can surface honest, relevant experience for each job.
2. **Tailoring.** A per-posting run that drafts a resume from the bank, checks every claim against it with an independent pass, fixes what it can, and compiles the PDF.
The bank is the foundation. A tailored resume is one query against it.


## Requirements

- **[Claude Code](https://claude.com/claude-code)**
- **A LaTeX distribution** providing `pdflatex` plus the template's packages (`titlesec`,
  `marvosym`, `enumitem`, `fullpage`, `fancyhdr`, `tabularx`, `hyperref`):
    - Debian/Ubuntu: `sudo apt install texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended`
    - Arch (btw): `sudo pacman -S texlive-latexextra texlive-fontsrecommended`
    - Fedora: `sudo dnf install texlive-scheme-medium`
    - macOS: `brew install --cask mactex` (or `basictex`, then `sudo tlmgr install titlesec marvosym enumitem`)
    - Windows: run the project under [WSL](https://learn.microsoft.com/windows/wsl/install) and follow the Debian/Ubuntu line
- **poppler-utils** (provides `pdfinfo` and `pdftotext`) for page-count checking and for
  reading your PDF resumes during onboarding:
    - Debian/Ubuntu: `sudo apt install poppler-utils`
    - Arch (btw): `sudo pacman -S poppler`
    - Fedora: `sudo dnf install poppler-utils`
    - macOS: `brew install poppler`
    - Windows: under WSL, follow the Debian/Ubuntu line
- **Python 3.10+**. The helper scripts are only standard-library.

Run `/setup` inside Claude Code to check all of this at once; it prints the install
command for your OS for anything missing. Without the LaTeX/poppler tools the pipeline
still runs, but it skips the compile and page-fit checks, so install them for the full
experience.


## Commands


| Command | What it does |
| --- | --- |
| `/setup` | Checks your machine has the [requirements](#requirements); prints the install command for your OS for anything missing. |
| `/onboard` | One-time setup. Reads your existing resumes/notes and builds your evidence bank, asking a few questions to fill the gaps. |
| `/tailor <posting>` | Per job. Drafts, self-checks, and compiles a resume tailored to one posting. |
| `/bank-map` | Refresh the bank's index after you edit your experience by hand. |

Everything a run produces lands in its own folder under `applications/`, so tailoring for
two jobs never collides.

## Setup

1. **Clone the repo** and open Claude Code in the project folder.

2. **Build your evidence bank.** Put your existing resumes and any other career material
   (project notes, brag docs, performance reviews; PDF, Markdown, plain text, or LaTeX)
   into `bank/sources/`, then run:

   ```
   /onboard
   ```

   It reads everything you gave it, structures your history into the bank, and asks a short
   set of questions: the things only you can answer (a real number behind an accomplishment,
   which of two dates is right) that make the result stronger. Answer what you can; skip the
   rest. The more resumes and notes you give it, the richer the bank.

   You can also paste a resume directly, or point it at files: `/onboard path/to/resume.pdf`.

That's it, you're ready to tailor. (Prefer to write the bank by hand? Create
`bank/experience_bank.md` and `bank/profile.json` following `spec/bank_format.md`, then run
`/bank-map`.)

## The bank

`bank/` is the asset everything else consumes. It holds your career in two layers, an
index, and the raw material:

- `experience_bank.md`, the evidence layer: every role and project as units of real
  work, with the facts behind each (systems, decisions, numbers, tools) in plain text
  under their real names. It is the only source of facts for resume claims; if an
  outcome isn't written here, no resume will mention it.
- `profile.json`, the record layer: name, contact, employers, dates, titles and their
  honest variants, education. Only the renderer reads it, the model never does, and
  where the two files state the same fact, this one wins.
- `evidence_map.md`, a derived index the drafter plans from: which evidence covers
  which kind of requirement, and what the bank simply doesn't have. `/bank-map`
  rebuilds it after you edit the bank by hand.
- `sources/`, the resumes and notes you onboarded, kept as they arrived.

The shape is inspired by [Karpathy's LLM wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
immutable sources beneath an LLM-maintained knowledge base, here with your career as
the domain. The bank compounds; each role, project, or number you add is material
every future resume can draw on. `spec/bank_format.md` is the contract.

## Tailoring a resume

Give `/tailor` a job posting in whichever form you have:

```
/tailor https://company.com/careers/the-job      # a URL
/tailor                                           # then paste the posting text
/tailor applications/<id>                          # re-tailor a saved posting
```

The run drafts a resume from your bank, has an independent pass check it against the posting
and your bank, applies fixes, and compiles the PDF. Every draft is compiled and measured as
it's written, and the run isn't done until every check comes back clean:

- the content validates against the resume schema and the LaTeX compiles
- the page fills exactly one page, measured from the PDF itself, in both directions
  (no overflow, no under-fill)
- craft lints catch an over-long bullet or two bullets in a role opening on the same verb
- a keyword gate diffs the posting's keywords against your bank, the draft, and the gap
  report: a true skill surfaces under the posting's spelling, and anything the bank can't
  back is recorded as a gap instead

When it finishes it hands you the exact path:

```
applications/2026-06-30_acme_data-engineer/
  Resume_YourName_Acme.pdf  ← your tailored, one-page resume, named for uploading
  README.md                 ← the run summary: verdict, salary, stack, posting link
  gaps.md                   ← honest notes: gaps it couldn't fill, adjacent experience it surfaced
  jd.txt                    ← the exact posting it was tailored to
  .run/                     ← the pipeline's working state (structured content, reviews)
```

Read `gaps.md` before you apply. It tells you where your experience is thin for this role
and what to be ready to speak to. Nothing is ever papered over.

Re-running `/tailor` on the same posting reuses its folder. `applications/index.md` tracks
everything you've tailored.


## Where this is going

The bank is the asset; most of what's ahead is new consumers of the same truth, each
read-only over the bank and held to the same grounding gate. Rough order of interest,
not a schedule:

- **More templates.** The renderer's template contract is small and documented
  (`ops/templates/README.md`).
- **Cover letters and application answers.** "Describe a time you..." boxes are bank
  queries: the strongest true story, framed to the question.
- **JD triage.** Score how well the bank covers a posting before spending a full run
  on it.
- **Premade resumes.** A standing set of archetype-tailored resumes for when there is
  no time to tailor.
- **Form filling.** Map known facts into the application form, flag every field it
  can't back, and stop at the submit button; submitting stays human.
- **A local web view** over the bank and the application ledger, with outcome tracking.

## Your data stays yours

Your bank and your applications are personal, and the repo is configured to never commit
them: `bank/`, `applications/`, and anything derived from them are git-ignored. What lives
in version control is the *tool* (prompts, scripts, schemas).

## Project layout

```
bank/          YOUR data (git-ignored): experience_bank.md, profile.json, and the sources
               you onboarded. This is the single source of truth every resume draws from.
applications/  YOUR runs (git-ignored): one folder per job, each a self-contained archive.
spec/          The contracts: resume + bank formats, and the LaTeX template.
ops/           Standard-library scripts: source intake, bank checks, workspace setup,
               and render.py, which turns resume content into LaTeX (all escaping lives here).
.claude/       The pipeline itself: the skills, subagents, and the compile/format hook.
CLAUDE.md      The always-on objective every stage reads: maximum truthful match.
```

## The template

Resumes render with Jake Gutierrez's classic one-column LaTeX layout. The model never
writes LaTeX: it writes resume content as JSON, and `ops/render.py` turns that into
`.tex` deterministically. Every layout decision and all character escaping live in
code, so no content the model writes can break the formatting.

A template is one declarative module in `ops/templates/`: a `SKELETON` holding the
document layout with named slots, and `FRAGMENTS` holding the markup for each kind of
content. `jake.py` is the reference; `ops/templates/README.md` has the full contract
and the steps to add your own.

## Credits

The LaTeX resume template is adapted from Jake Gutierrez's widely used
[resume template](https://github.com/jakegut/resume), itself based on
[sb2nov/resume](https://github.com/sb2nov/resume). See `LICENSE` for this project's terms.
