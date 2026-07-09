"""Jake template, fully declarative: SKELETON owns layout, FRAGMENTS own markup.

No content and no logic; ops/render.py owns traversal and escaping. The skeleton
is filled by slot replacement (%%SLOT%%); fragments use printf-style placeholders
(%(name)s), so in a fragment a literal % is %%.
"""

SKELETON = r"""%-------------------------
% Resume in Latex
% Author : Jake Gutierrez
% Based off of: https://github.com/sb2nov/resume
% License : MIT
%------------------------
% NOTE: This is a pure presentation asset with named slots (%%SLOT%%).
% It is rendered by render.py; no model ever writes this file. Do not put
% content here. Edit only presentation (preamble, custom commands, section order).

\documentclass[letterpaper,11pt]{article}

\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\input{glyphtounicode}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% Adjust margins
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% Sections formatting
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

% Ensure that generate pdf is machine readable/ATS parsable
\pdfgentounicode=1

%-------------------------
% Custom commands
% Divergence from canonical Jake: the upstream form is
%   \item\small{ {#1 \vspace{-2pt}} }
% whose redundant inner group + embedded whitespace collide with \raggedright when a
% bullet fills exactly two lines with a near-full second line, inserting a phantom
% ~12pt (one baseline) below it. Flattening to a single group removes that structure
% while keeping the identical look (small text, -2pt tightening, ragged right).
\newcommand{\resumeItem}[1]{\item\small{#1}\vspace{-2pt}}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

%-------------------------------------------
%%%%%%  RESUME STARTS HERE  %%%%%%%%%%%%%%%%%%%%%%%%%%%%

\begin{document}

%----------HEADING----------
\begin{center}
    \textbf{\Large \scshape %%NAME%%} \\ \vspace{1pt}
    \small %%CONTACT%%
\end{center}

%%SKILLS%%
%%EXPERIENCE%%
%%PROJECTS%%
%%EDUCATION%%

%-------------------------------------------
\end{document}
"""

FRAGMENTS = {
    # contact line parts, joined by contact.sep
    "contact.sep": " $|$\n    ",
    "contact.text": "%(text)s",
    "contact.email": "\\href{mailto:%(url)s}{\\underline{%(text)s}}",
    "contact.link": "\\href{%(url)s}{\\underline{%(text)s}}",

    "dates.range": "%(start)s -- %(end)s",

    "skills.section": (
        "%%-----------TECHNICAL SKILLS-----------\n"
        "\\section{Technical Skills}\n"
        " \\begin{itemize}[leftmargin=0.15in, label={}]\n"
        "    \\small{\\item{\n"
        "%(rows)s\n"
        "    }}\n"
        " \\end{itemize}\n\n"
    ),
    "skills.row": "     \\textbf{%(category)s}{: %(items)s}",
    "skills.row_sep": " \\\\\n",
    "skills.item_sep": " $\\cdot$ ",

    "experience.section": (
        "%%-----------EXPERIENCE-----------\n"
        "\\section{Experience}\n"
        "  \\resumeSubHeadingListStart\n"
        "%(entries)s\n"
        "\n"
        "  \\resumeSubHeadingListEnd\n\n"
    ),
    "experience.entry": (
        "\n"
        "    \\resumeSubheading\n"
        "      {%(title)s}{%(dates)s}\n"
        "      {%(employer)s}{%(location)s}\n"
        "      \\resumeItemListStart\n"
        "%(bullets)s\n"
        "      \\resumeItemListEnd"
    ),
    "experience.bullet": "        \\resumeItem{%(text)s}",

    "projects.section": (
        "%%-----------PROJECTS-----------\n"
        "\\section{Projects}\n"
        "    \\resumeSubHeadingListStart\n"
        "%(entries)s\n"
        "\n"
        "    \\resumeSubHeadingListEnd\n\n"
    ),
    "projects.entry": (
        "\n"
        "      \\resumeProjectHeading\n"
        "          {%(head)s}{%(dates)s}\n"
        "          \\resumeItemListStart\n"
        "%(bullets)s\n"
        "          \\resumeItemListEnd"
    ),
    "projects.head": "\\textbf{%(name)s}",
    "projects.stack": " $|$ \\emph{%(stack)s}",
    "projects.bullet": "            \\resumeItem{%(text)s}",

    "education.section": (
        "%%-----------EDUCATION-----------\n"
        "\\section{Education}\n"
        "  \\resumeSubHeadingListStart\n"
        "%(entries)s\n"
        "%(coursework)s"
        "  \\resumeSubHeadingListEnd\n\n"
    ),
    "education.entry": (
        "    \\resumeSubheading\n"
        "      {%(degree)s}{%(dates)s}\n"
        "      {%(institution)s}{%(location)s}"
    ),
    "education.coursework": (
        "      \\resumeItemListStart\n"
        "        \\resumeItem{Relevant Coursework: %(items)s}\n"
        "      \\resumeItemListEnd\n"
    ),
}
