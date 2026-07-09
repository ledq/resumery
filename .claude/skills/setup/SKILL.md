---
name: setup
description: Check that this machine has everything the pipeline needs (pdflatex, poppler's pdfinfo/pdftotext, Python 3.10+). Run once after cloning, or whenever a compile or PDF read fails; when something is missing it prints the exact install command for this OS.
---

# /setup: environment check

Run the deterministic checker and relay its result:

```
python3 ops/env_check.py
```

- **Everything present** (exit 0): tell the user they are ready, and point at the next
  step: put existing resumes into `bank/sources/` and run `/onboard` (or, if the bank
  already exists, `/tailor <posting>`).
- **Something missing** (exit 4): show the install command the script printed and ask
  the user to run it themselves by typing `! <command>` in the prompt; installs need
  sudo or an interactive prompt, so never run the install yourself. Once they say it is
  installed, run the checker again to confirm.

Missing LaTeX/poppler is a degraded mode, not a hard stop: the pipeline still runs but
skips the compile and page-fit checks. Say so if the user chooses not to install.
