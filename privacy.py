"""Keep the phone's network address out of anything a model might read.

Calls only hand the model call state and the transcript (the transcript is kept on
purpose). Logs and error text are the leak path: pjsua and exceptions happily print
IPs, SIP URIs, SDP candidates, auth headers and SRTP keys. Everything that reaches
stderr / a log file / a tool result goes through redact() first; install_stderr()
wraps sys.stderr so stray prints and tracebacks are scrubbed too.

Matching is not anchored to line start: a header or SDP field buried after a log or
exception prefix ("failed: Authorization: ...") is caught, and folded continuation
lines of a sensitive SIP header (leading whitespace) are masked as well.

This lowers the risk of network info entering the model's context by accident.
It is NOT isolation from an admin on the same host: anyone with root (including a
model running as root) can still read raw process state or capture packets. Output
written straight to fd 2 by C code (outside pjsua's log writer) is not covered.
"""
import atexit
import io
import re
import sys

MASK = "<redacted>"

_HDRS = (r"Via|Contact|Record-Route|Route|From|To|Received|Authorization|"
         r"Proxy-Authorization|WWW-Authenticate|Proxy-Authenticate|Authentication-Info|"
         r"X-Real-IP|X-Forwarded-For|P-Asserted-Identity|P-Preferred-Identity|"
         r"Remote-Party-ID|Path|Service-Route|Refer-To|Referred-By|Reply-To|Call-ID")
# full header name anywhere after a boundary (line start, space, punctuation)
_HDR_RE = re.compile(r"(?P<k>(?:^|(?<=[\s:;,(\[{\"'>|]))(?:" + _HDRS + r")\s*:)[^\r\n]*",
                     re.IGNORECASE | re.MULTILINE)
# compact one-letter forms (v: m: f: t: i:) only at line start, to spare ordinary text
_COMPACT_RE = re.compile(r"^(?P<k>[ \t]*[vmfti][ \t]*:)[^\r\n]*", re.IGNORECASE | re.MULTILINE)
_HDR_LINE_RE = re.compile(r"(?:^|[\s:;,(\[{\"'>|])(?:" + _HDRS + r")\s*:|^[ \t]*[vmfti][ \t]*:",
                          re.IGNORECASE)

# SDP fields, anywhere on the line
_SDP_RE = re.compile(
    r"(?P<k>(?<![\w-])(?:a=candidate:|a=remote-candidates:|a=rtcp:|a=crypto:|a=fingerprint:|"
    r"a=ice-ufrag:|a=ice-pwd:|a=key-mgmt:))[^\r\n]*", re.IGNORECASE)
_SDP_CO_RE = re.compile(r"(?P<k>(?<![\w-])[co]=)[^\r\n]*\bIN\s+IP[46]\b[^\r\n]*", re.IGNORECASE)

_URI_RE = re.compile(r"\b(sips?|tel):[^\s<>\"';,]+", re.IGNORECASE)
_PARAM_RE = re.compile(
    r"\b(received|rport|maddr|branch|tag|nonce|cnonce|response|opaque|realm|username|"
    r"ufrag|pwd|password|passwd|secret)\s*=\s*(\"[^\"]*\"|[^\s;,>\"]+)", re.IGNORECASE)
_INLINE_KEY_RE = re.compile(r"\binline:[A-Za-z0-9+/=|:^]+")
_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?![\d.])")
_IPV6_RE = re.compile(
    r"\[?(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}(?:[0-9A-Fa-f]{1,4}|(?:\d{1,3}\.){3}\d{1,3})?"
    r"(?:%\w+)?\]?(?::\d{1,5})?(?![\w:])")


def _v6_sub(m):
    s = m.group(0)
    core = s.strip("[]")
    # leave timestamps like 12:34:56 alone; a real v6 has '::', hex letters or 4+ colons
    if "::" in core or core.count(":") >= 4 or re.search(r"[A-Fa-f]", core):
        return MASK
    return s


def _scrub_line(s):
    s = _HDR_RE.sub(lambda m: m.group("k") + " " + MASK, s)
    s = _COMPACT_RE.sub(lambda m: m.group("k") + " " + MASK, s)
    s = _SDP_RE.sub(lambda m: m.group("k") + MASK, s)
    s = _SDP_CO_RE.sub(lambda m: m.group("k") + MASK, s)
    s = _URI_RE.sub(lambda m: m.group(1) + ":" + MASK, s)
    s = _PARAM_RE.sub(lambda m: m.group(1) + "=" + MASK, s)
    s = _INLINE_KEY_RE.sub("inline:" + MASK, s)
    s = _IPV4_RE.sub(MASK, s)
    s = _IPV6_RE.sub(_v6_sub, s)
    return s


class Redactor:
    """Line-wise scrubber that remembers whether the previous line was a sensitive
    header, so folded continuation lines (leading space/tab) get masked too."""

    def __init__(self):
        self._in_hdr = False

    def feed(self, text):
        out = []
        for line in str(text).splitlines(keepends=True):
            body = line.rstrip("\r\n")
            nl = line[len(body):]
            if self._in_hdr and body[:1] in (" ", "\t") and body.strip():
                out.append(body[:len(body) - len(body.lstrip())] + MASK + nl)
                continue
            self._in_hdr = bool(_HDR_LINE_RE.search(body))
            out.append(_scrub_line(body) + nl)
        return "".join(out)


def redact(text):
    if text is None:
        return text
    return Redactor().feed(text)


class _RedactingStream(io.TextIOBase):
    """Line-buffered wrapper: scrubs each complete line before passing it on."""

    def __init__(self, inner):
        self._inner = inner
        self._buf = ""
        self._r = Redactor()

    def write(self, s):
        self._buf += s
        if "\n" in self._buf:
            head, self._buf = self._buf.rsplit("\n", 1)
            self._inner.write(self._r.feed(head + "\n"))
        return len(s)

    def flush(self):
        # never release a partial line: half an address could pass the regexes and the
        # other half arrive later. The tail is emitted (scrubbed) only by close().
        self._inner.flush()

    def close(self):
        if self._buf:
            self._inner.write(self._r.feed(self._buf))
            self._buf = ""
        self._inner.flush()

    def fileno(self):
        return self._inner.fileno()

    def isatty(self):
        return self._inner.isatty()

    @property
    def encoding(self):
        return getattr(self._inner, "encoding", "utf-8")


def install_stderr():
    """Scrub everything Python writes to stderr (prints, logging, tracebacks)."""
    if not isinstance(sys.stderr, _RedactingStream):
        sys.stderr = _RedactingStream(sys.stderr)
        atexit.register(sys.stderr.close)   # scrubbed tail of an unterminated last line
