"""Balanced-tag extraction of the page's blocks, so the six-theme layout is rebuilt from main's page each run."""
import re

VOID = {"img", "br", "hr", "input", "meta", "link", "source", "wbr", "area", "col", "embed", "param", "track"}


def end_of(s, i):
    """Index just past the element that starts at s[i] ('<tag ...')."""
    tag = re.match(r"<([a-zA-Z0-9]+)", s[i:]).group(1)
    if tag.lower() in VOID:
        return s.index(">", i) + 1
    op, cl = re.compile(r"<%s(?=[\s>/])" % tag), re.compile(r"</%s\s*>" % tag)
    depth, pos = 0, i
    while True:
        o, c = op.search(s, pos), cl.search(s, pos)
        if c is None:
            raise ValueError("unclosed <%s> at %d" % (tag, i))
        if o and o.start() < c.start():
            depth += 1; pos = o.end()
        else:
            depth -= 1; pos = c.end()
            if depth == 0:
                return pos


def find(s, pat, start=0):
    """(start, end) of the element whose opening tag matches the regex pat."""
    m = re.compile(pat).search(s, start)
    if not m:
        raise ValueError("not found: " + pat)
    return m.start(), end_of(s, m.start())


def get(s, pat, start=0):
    a, b = find(s, pat, start)
    return s[a:b]


def inner(el):
    """The inner HTML of an element string."""
    a = el.index(">") + 1
    b = el.rindex("</")
    return el[a:b]


def children(html):
    """Top-level elements of an HTML fragment, in order (comments and text between them dropped)."""
    out, i = [], 0
    while True:
        j = html.find("<", i)
        if j < 0:
            return out
        if html.startswith("<!--", j):
            i = html.index("-->", j) + 3; continue
        if html.startswith("</", j):
            raise ValueError("stray closing tag at %d: %r" % (j, html[j:j + 40]))
        k = end_of(html, j)
        out.append(html[j:k]); i = k


def attr(el, name):
    m = re.match(r"<[^>]*\s%s=\"([^\"]*)\"" % name, el)
    return m.group(1) if m else None


def tagname(el):
    return re.match(r"<([a-zA-Z0-9]+)", el).group(1).lower()
