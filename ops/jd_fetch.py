#!/usr/bin/env python3
"""Fetch a JD: URL -> <stage_dir>/jd.txt (posting text) + <stage_dir>/url (the address).

Used by the /tailor skill; the staged file is the canonical copy the pipeline receives.
ATS-hosted postings resolve through the ATS's public JSON API (see HANDLERS) instead of
scraping what is often a JS shell. Transient failures (429, 5xx, timeouts) retry with
backoff; permanent ones (403, 404, too little text) fail fast to the paste fallback.

usage : jd_fetch.py <url> <stage_dir>
exit  : 0 ok / 2 usage / 4 fetch failed or too little text (likely JS-rendered or
        blocked; the skill asks the user to paste the posting instead)
"""
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

MIN_CHARS = 200  # under this, assume a JS-rendered shell or a block page

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) resume-tailor/jd_fetch",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en;q=0.9",
}

MAX_ATTEMPTS = 4          # 1 try + 3 retries; worst case ~14s of waiting
BACKOFF_START = 1.0       # seconds; doubles each retry
RETRY_AFTER_CAP = 10.0    # never honor a server's Retry-After beyond this

SKIP = {"script", "style", "noscript", "svg", "head", "template"}
BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "h1", "h2", "h3",
         "h4", "h5", "h6", "section", "article", "header", "footer"}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self._skip += 1
        elif tag in BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP and self._skip:
            self._skip -= 1
        elif tag in BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.out.append(data)


def retry_delay(attempt, retry_after):
    if retry_after:
        try:
            return min(float(retry_after), RETRY_AFTER_CAP)
        except ValueError:
            pass  # an HTTP-date Retry-After; fall through to backoff
    return BACKOFF_START * (2 ** attempt) + random.uniform(0, 0.5)


def fetch(url):
    """GET with retries on transient failures. Returns (content_type, body_text)."""
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(MAX_ATTEMPTS):
        retry_after = None
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return (resp.headers.get_content_type(),
                        resp.read().decode(charset, errors="replace"))
        except urllib.error.HTTPError as ex:
            if ex.code != 429 and ex.code < 500:
                raise  # 403/404/...: retrying a block or a dead link changes nothing
            retry_after = ex.headers.get("Retry-After")
            err = ex
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            err = ex  # DNS hiccup, refused connection, timeout: worth another try
        if attempt + 1 == MAX_ATTEMPTS:
            raise err
        delay = retry_delay(attempt, retry_after)
        sys.stderr.write(f"jd_fetch.py: {err}; retrying in {delay:.1f}s "
                         f"({attempt + 2}/{MAX_ATTEMPTS})\n")
        time.sleep(delay)


def html_to_text(raw):
    p = TextExtractor()
    p.feed(raw)
    return "".join(p.out)


# --- ATS handlers -------------------------------------------------------------
# Each handler recognizes one ATS from the URL (or fetched page) and returns the
# posting text, or None to decline; main() tries HANDLERS in order, then the generic
# page fetch. Add new ATSes here.

GH_BOARD_PATTERNS = [  # board token, found in the URL or the de-escaped page HTML
    re.compile(r"greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)/jobs/"),
    re.compile(r"greenhouse\.io/embed/job_board(?:/js)?\?(?:[^\"'\s]*&)?for=([A-Za-z0-9_-]+)"),
    re.compile(r"boards\.greenhouse\.io/([A-Za-z0-9_-]+)"),
]


def fetch_greenhouse(url):
    """Greenhouse postings: *.greenhouse.io/<board>/jobs/<id> URLs and gh_jid= embeds."""
    parts = urllib.parse.urlparse(url)
    board = job_id = None
    m = re.match(r"/([^/]+)/jobs/(\d+)", parts.path)
    if parts.hostname and parts.hostname.endswith("greenhouse.io") and m:
        board, job_id = m.group(1), m.group(2)
    else:
        job_id = (urllib.parse.parse_qs(parts.query).get("gh_jid") or [None])[0]
        if not job_id:
            return None  # no Greenhouse marks on this URL; decline
        page = fetch(url)[1].replace("\\/", "/")  # embed page names its board (JSON-escaped)
        for pat in GH_BOARD_PATTERNS:
            bm = pat.search(page)
            if bm:
                board = bm.group(1)
                break
        if not board:
            return None
    data = json.loads(fetch(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}")[1])
    body = html_to_text(html.unescape(data["content"]))
    head = "\n".join(x for x in (data.get("title"),
                                 (data.get("location") or {}).get("name")) if x)
    sys.stderr.write(f"jd_fetch.py: greenhouse posting, board '{board}', job {job_id}\n")
    return f"{head}\n\n{body}"


def fetch_workday(url):
    """Workday postings: <tenant>.<wd#>.myworkdayjobs.com/[<locale>/]<site>/job/<path>."""
    parts = urllib.parse.urlparse(url)
    host = parts.hostname or ""
    m = re.match(r"^/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)/job/(.+)$", parts.path)
    if not host.endswith(".myworkdayjobs.com") or not m:
        return None
    tenant, site, job_path = host.split(".")[0], m.group(1), m.group(2)
    data = json.loads(fetch(
        f"https://{host}/wday/cxs/{tenant}/{site}/job/{job_path}")[1])["jobPostingInfo"]
    body = html_to_text(data["jobDescription"])
    head = "\n".join(x for x in (data.get("title"), data.get("location")) if x)
    sys.stderr.write(f"jd_fetch.py: workday posting, tenant '{tenant}', site '{site}'\n")
    return f"{head}\n\n{body}"


HANDLERS = [fetch_greenhouse, fetch_workday]


def main():
    if len(sys.argv) != 3 or not Path(sys.argv[2]).is_dir():
        sys.stderr.write("usage: jd_fetch.py <url> <stage_dir>  (stage_dir must exist)\n")
        return 2
    url = sys.argv[1]

    text = None
    for handler in HANDLERS:
        try:
            text = handler(url)
        except Exception as ex:
            sys.stderr.write(f"jd_fetch.py: {handler.__name__} gave up ({ex}); "
                             "trying the generic page fetch\n")
            text = None
        if text:
            break

    if text is None:
        try:
            ctype, raw = fetch(url)
        except Exception as ex:
            sys.stderr.write(f"jd_fetch.py: fetch failed: {ex}\n")
            return 4
        if "html" in ctype or "<html" in raw[:2000].lower() or "<div" in raw[:2000].lower():
            text = html_to_text(raw)
        else:
            text = raw

    # collapse runs of blank lines to one
    out, blank = [], 0
    for line in (l.strip() for l in text.splitlines()):
        blank = blank + 1 if not line else 0
        if blank <= 1:
            out.append(line)
    text = "\n".join(out).strip()

    if len(text) < MIN_CHARS:
        sys.stderr.write(
            f"jd_fetch.py: only {len(text)} chars of text extracted; the page is likely "
            "JS-rendered or blocked the fetch. Ask the user to paste the posting.\n")
        return 4

    stage = Path(sys.argv[2])
    (stage / "jd.txt").write_text(text + "\n", encoding="utf-8")
    (stage / "url").write_text(sys.argv[1] + "\n", encoding="utf-8")
    sys.stderr.write(f"jd_fetch.py: staged {len(text)} chars into {stage}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
