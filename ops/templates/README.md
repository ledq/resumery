# Templates

A template is one Python module in this directory, and it holds presentation only.
`ops/render.py` is the engine: it walks the resume content and the profile record,
escapes every string, and asks the template for markup. Templates contain no logic
and never see raw model output.

Each module exposes two objects:

- `SKELETON`: the complete LaTeX document as one string, with six named slots the
  engine replaces: `%%NAME%%`, `%%CONTACT%%`, `%%SKILLS%%`, `%%EXPERIENCE%%`,
  `%%PROJECTS%%`, `%%EDUCATION%%`. Preamble, custom commands, margins, and section
  order all live here. Rendering fails with the missing slot named if one is absent.
- `FRAGMENTS`: a dict of printf-style snippets (`%(name)s` placeholders; a literal
  `%` is written `%%`) that the engine fills as it walks the content. The engine
  calls a fixed set of keys, so a new template defines every key below; `jake.py`
  is the reference for the markup each one carries.

Values arrive already escaped; fragments add markup around them, never escaping.

## The fragment keys

| Key | Placeholders | Fills |
| --- | --- | --- |
| `contact.sep` | none | joiner between contact parts |
| `contact.text` | `text` | phone and base location |
| `contact.email` | `url`, `text` | email link |
| `contact.link` | `url`, `text` | each profile link (text is the label) |
| `dates.range` | `start`, `end` | every date range (roles, education) |
| `skills.section` | `rows` | the Skills section shell |
| `skills.row` | `category`, `items` | one category row |
| `skills.row_sep` | none | joiner between rows |
| `skills.item_sep` | none | joiner between items in a row |
| `experience.section` | `entries` | the Experience section shell |
| `experience.entry` | `title`, `dates`, `employer`, `location`, `bullets` | one role |
| `experience.bullet` | `text` | one bullet |
| `projects.section` | `entries` | the Projects section shell (omitted when no projects) |
| `projects.entry` | `head`, `dates`, `bullets` | one project |
| `projects.head` | `name` | project name |
| `projects.stack` | `stack` | appended to the head when a stack is given |
| `projects.bullet` | `text` | one bullet |
| `education.section` | `entries`, `coursework` | the Education section shell |
| `education.entry` | `degree`, `dates`, `institution`, `location` | one degree |
| `education.coursework` | `items` | the optional coursework line |

## Adding a template

1. Copy `jake.py` to `<name>.py` and rework `SKELETON` and `FRAGMENTS`, keeping
   every fragment key.
2. Register the module in the `TEMPLATES` dict in `ops/render.py` and point
   `DEFAULT_TEMPLATE` at it.
3. Verify against a real workspace: `python3 ops/render.py applications/<id>`, then
   `bash .claude/hooks/check.sh applications/<id>` for the compile and page checks.
