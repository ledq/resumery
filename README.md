# resumery
 
Turn your career history into a structured evidence bank, then tailor a truthful one-page resume to any job posting. Runs inside Claude Code.

## What it is
 
resumery has two parts:
 
1. **The bank.** A persistent, structured record of your career: every role, project, and design decision, with provenance. You build it once from your existing resumes and grow it over time. Because it holds more than any single resume does, tailoring can surface honest, relevant experience for each job.
2. **Tailoring.** A per-posting run that drafts a resume from the bank, checks every claim against it with an independent pass, fixes what it can, and compiles the PDF.
The bank is the foundation. A tailored resume is one query against it.


## Requirements

- **[Claude Code](https://claude.com/claude-code)**, where the whole pipeline runs. A Claude
  subscription is enough; no API key required.
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

2. **Build your evidence bank.** Put one or more of your existing resumes (PDF, Markdown,
   plain text, or LaTeX) into `bank/sources/`, then run:

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

## Tailoring a resume

Give `/tailor` a job posting in whichever form you have:

```
/tailor https://company.com/careers/the-job      # a URL
/tailor                                           # then paste the posting text
/tailor applications/<id>                          # re-tailor a saved posting
```

The run drafts a resume from your bank, has an independent pass check it against the posting
and your bank, applies fixes, and compiles the PDF. When it finishes it hands you the exact
path:

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

> Two-page resume? Set `RESUME_MAX_PAGES=2` in the environment before the run.

## The rule: claims vs. framing

Everything on a generated resume traces back to your bank. The pipeline draws a hard line:

- **Claims** are checkable facts: titles, employers, dates, whether an accomplishment
  happened, the numbers behind it. These must be true, always. This layer has no wiggle room.
- **Framing** is how true work is presented: which experience leads, which bullets are
  chosen, the words describing real work. This is optimized freely for each posting.

Reframing your real experience to fit a job is the whole point. Inventing experience,
outcomes, or numbers is the one thing the system will not do; an independent grounding
check gates every claim against your bank before a resume ships.

## Your data stays yours

Your bank and your applications are personal, and the repo is configured to never commit
them: `bank/`, `applications/`, and anything derived from them are git-ignored. What lives
in version control is the *tool* (prompts, scripts, schemas), never your career history or
who you applied to. If you fork or publish this repo, your data does not go with it.

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

## Credits

The LaTeX resume template is adapted from Jake Gutierrez's widely used
[resume template](https://github.com/sb2nov/resume). See `LICENSE` for this project's terms.
