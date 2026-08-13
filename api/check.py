"""POST a draft here, get back the findings the CLI would print, as JSON.

Vercel serves the ``handler`` class below at ``/api/check``.

The linter itself lives at the repo root -- ``check_engine`` runs the rules,
``rules.checks`` registers the ten of them, and ``cli`` owns the normalising
and scoring so the web report and ``python cli.py`` can never disagree. This
file is one directory below all of that, so the root goes on ``sys.path``
first. ``vercel.json`` carries the matching ``includeFiles`` glob; without it
the root modules never reach the deployed function and every request 500s.

Stdlib only, like the rest of the tool. Nothing is stored: the draft lives in
the request body and in the response, and nowhere else.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

#: Longer than any real submission; past this the request is rejected, not truncated.
MAX_TEXT = 200_000

#: meta keys the rules actually read. Anything else is dropped rather than passed on.
META_KEYS = ("links", "required_links", "hard_rules")


def _find_repo_root():
    """Nearest ancestor of this file holding check_engine.py, else None.

    Walks up rather than hardcoding ``..`` so the function works the same when
    Vercel rebases the project into a task root as it does from a checkout.
    """
    candidates = []
    path = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        candidates.append(path)
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    candidates.append(os.getcwd())
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "check_engine.py")):
            return candidate
    return None


_ROOT = _find_repo_root()
if _ROOT and _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Imported at cold start so a broken deployment fails loudly on the first
# request instead of quietly reporting a clean draft.
_IMPORT_ERROR = None
try:
    import check_engine
    import cli
    import rules.checks  # noqa: F401  -- importing it registers the ten rules
except Exception as exc:  # pragma: no cover - only fires on a broken deploy
    _IMPORT_ERROR = "%s: %s" % (type(exc).__name__, exc)


def analyse(text, meta):
    """Run the rules over ``text`` and return the report the browser renders.

    Mirrors ``cli.analyse`` field for field, minus the file read: same
    normalising, same sort, same score, so the page and the terminal agree.
    """
    findings = [cli.normalise(f, text) for f in (check_engine.run_checks(text, meta) or [])]
    findings.sort(key=lambda f: (cli.SEVERITIES.index(f["severity"]), f["line"] or 0))

    engine_score = getattr(check_engine, "score", None)
    score = engine_score(findings) if callable(engine_score) else cli.compute_score(findings)
    return {
        "score": int(score),
        "counts": cli.count_by_severity(findings),
        "findings": findings,
    }


def _clean_meta(raw):
    """Keep only the keys the rules read; treat a missing or null meta as {}."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("meta must be a JSON object")
    return {key: raw[key] for key in META_KEYS if raw.get(key) is not None}


class handler(BaseHTTPRequestHandler):
    """POST {text, meta} -> {score, counts, findings}."""

    server_version = "submission-check"

    # -- plumbing ---------------------------------------------------------

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _fail(self, status, message):
        self._send(status, {"error": message})

    def _body(self):
        """Read the request body, or raise ValueError with a usable message."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("Content-Length is not a number")
        if length <= 0:
            raise ValueError("Request body is empty; POST {\"text\": \"...\"}")
        if length > MAX_TEXT * 2:
            raise ValueError("Request body is larger than %d bytes" % (MAX_TEXT * 2))
        return self.rfile.read(length)

    # -- routes -----------------------------------------------------------

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        """A health check that also proves the rules loaded."""
        if _IMPORT_ERROR:
            return self._fail(500, "Linter failed to import: %s" % _IMPORT_ERROR)
        return self._send(
            200,
            {
                "ok": True,
                "rules": [rule.rule_id for rule in check_engine.registry()],
                "usage": 'POST {"text": "your draft", "meta": {}} to this URL',
            },
        )

    def do_POST(self):
        if _IMPORT_ERROR:
            return self._fail(500, "Linter failed to import: %s" % _IMPORT_ERROR)

        try:
            raw = self._body()
        except ValueError as exc:
            return self._fail(400, str(exc))

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            return self._fail(400, "Body is not valid UTF-8 JSON: %s" % exc)

        if not isinstance(payload, dict):
            return self._fail(400, "Body must be a JSON object with a text field")

        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._fail(400, "Nothing to check: text is missing or empty")
        if len(text) > MAX_TEXT:
            return self._fail(
                400, "Draft is %d characters; the limit is %d" % (len(text), MAX_TEXT)
            )

        try:
            meta = _clean_meta(payload.get("meta"))
        except ValueError as exc:
            return self._fail(400, str(exc))

        try:
            report = analyse(text, meta)
        except Exception as exc:  # a rule raised: report it rather than a blank page
            return self._fail(500, "%s: %s" % (type(exc).__name__, exc))

        return self._send(200, report)

    def log_message(self, fmt, *args):
        """Keep the draft out of the logs; Vercel records the request line anyway."""
