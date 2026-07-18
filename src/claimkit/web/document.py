r"""Render a LaTeX/Markdown draft to a lean reading view with provenance spans.

The author marks a provenanced number or statement inline:

* LaTeX:    ``\\prov{<id>}{<text>}``  (define ``\\newcommand{\\prov}[2]{#2}`` so the
  PDF is unaffected)
* Markdown: ``[<text>](prov:<id>)``

``<id>`` is a claim or result id in the claimkit graph. :func:`render_document`
turns each marker into a ``<span class="prov" data-id="<id>">`` the web view
colours by that node's status and makes click-through; :func:`extract_ref_ids`
lists the referenced ids so dangling references can be flagged.

The LaTeX pass is deliberately lightweight (a readable prose view, not a
pixel-faithful compile): comments are dropped, sectioning becomes headings,
common formatting macros are unwrapped, inline math is shown verbatim.
"""

from __future__ import annotations

import html
import re

_PROV_TOKEN = "\x00PROV{}\x00"  # noqa: S105 - a text placeholder, not a secret


def _match_braces(text: str, open_at: int) -> tuple[str, int]:
    """Return the content of a ``{...}`` group starting at ``open_at`` and its end.

    Args:
        text: The full string.
        open_at: Index of the opening ``{``.

    Returns:
        ``(inner, end)`` where ``inner`` excludes the braces and ``end`` is the
        index just past the closing ``}``.

    Raises:
        ValueError: If the braces are unbalanced.
    """
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_at + 1 : i], i + 1
    raise ValueError("unbalanced braces")


def _extract_latex_prov(text: str) -> tuple[str, list[tuple[str, str]]]:
    r"""Replace ``\prov{id}{content}`` with tokens; return (text, [(id, content)])."""
    refs: list[tuple[str, str]] = []
    out = []
    i = 0
    while True:
        m = re.search(r"\\prov\s*\{", text[i:])
        if not m:
            out.append(text[i:])
            break
        start = i + m.start()
        out.append(text[i:start])
        id_open = i + m.end() - 1
        prov_id, after_id = _match_braces(text, id_open)
        if after_id >= len(text) or text[after_id] != "{":
            # not the 2-arg form; emit literally and move on
            out.append(text[start:after_id])
            i = after_id
            continue
        content, after_content = _match_braces(text, after_id)
        out.append(_PROV_TOKEN.format(len(refs)))
        refs.append((prov_id.strip(), content))
        i = after_content
    return "".join(out), refs


def _extract_markdown_prov(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Replace ``[text](prov:id)`` with tokens; return (text, [(id, content)])."""
    refs: list[tuple[str, str]] = []

    def _sub(m: re.Match) -> str:
        refs.append((m.group(2).strip(), m.group(1)))
        return _PROV_TOKEN.format(len(refs) - 1)

    out = re.sub(r"\[([^\]]*)\]\(prov:([^)]+)\)", _sub, text)
    return out, refs


_LATEX_UNWRAP = re.compile(r"\\(?:emph|textbf|textit|texttt|gls|glspl|text|mbox|ensuremath)\s*\{")
_LATEX_DROP_ARG = re.compile(r"\\(?:label|cite[a-z]*|ref|eqref|footnote|index)\s*\{[^{}]*\}")


def _latex_prose_to_html(text: str) -> str:
    """Very small LaTeX->HTML prose pass (headings, unwrapping, paragraphs)."""
    text = re.sub(r"(?<!\\)%.*", "", text)  # comments
    text = _LATEX_DROP_ARG.sub("", text)
    # unwrap \emph{x} etc. -> x (repeat for simple nesting)
    for _ in range(4):
        new = []
        i = 0
        while True:
            m = _LATEX_UNWRAP.search(text, i)
            if not m:
                new.append(text[i:])
                break
            new.append(text[i : m.start()])
            inner, end = _match_braces(text, m.end() - 1)
            new.append(inner)
            i = end
        text = "".join(new)
    headings: list[tuple[str, str]] = []
    for cmd, tag in (("section", "h2"), ("subsection", "h3"), ("subsubsection", "h4")):
        while True:
            m = re.search(r"\\" + cmd + r"\*?\s*\{", text)
            if not m:
                break
            inner, end = _match_braces(text, m.end() - 1)
            token = f"\x00H{len(headings)}\x00"
            headings.append((tag, inner))
            text = text[: m.start()] + token + text[end:]
    # strip a few structural commands, keep their text
    text = re.sub(r"\\(?:begin|end)\s*\{[^{}]*\}", "", text)
    text = text.replace(r"\item", "• ")
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)  # drop remaining bare macros
    text = text.replace("~", " ").replace("\\&", "&").replace("\\%", "%").replace("---", "—").replace("--", "–")  # noqa: RUF001
    text = text.replace("{", "").replace("}", "")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    rendered = []
    for p in paras:
        body = html.escape(p)
        for idx, (tag, inner) in enumerate(headings):
            body = body.replace(f"\x00H{idx}\x00", f"</p><{tag}>{html.escape(inner)}</{tag}><p>")
        rendered.append(f"<p>{body}</p>")
    return "\n".join(rendered)


def _markdown_prose_to_html(text: str) -> str:
    """Minimal Markdown->HTML (headings, bold/italic, paragraphs)."""
    blocks = []
    for raw in re.split(r"\n\s*\n", text):
        para = raw.strip()
        if not para:
            continue
        hm = re.match(r"(#{1,4})\s+(.*)", para)
        if hm:
            level = min(len(hm.group(1)) + 1, 4)
            blocks.append(f"<h{level}>{html.escape(hm.group(2))}</h{level}>")
            continue
        body = html.escape(para)
        body = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", body)
        body = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", body)
        blocks.append(f"<p>{body}</p>")
    return "\n".join(blocks)


def render_document(text: str, fmt: str) -> tuple[str, list[str]]:
    """Render a draft to reading-view HTML with provenance spans.

    Args:
        text: The raw LaTeX or Markdown source.
        fmt: ``"latex"`` or ``"markdown"``.

    Returns:
        ``(html, ref_ids)`` — the rendered HTML and the provenance ids referenced
        (in document order, duplicates kept).
    """
    if fmt == "latex":
        stripped, refs = _extract_latex_prov(text)
        body = _latex_prose_to_html(stripped)
        inner_render = _latex_prose_to_html
    else:
        stripped, refs = _extract_markdown_prov(text)
        body = _markdown_prose_to_html(stripped)
        inner_render = _markdown_prose_to_html

    for idx, (prov_id, content) in enumerate(refs):
        inner = inner_render(content)
        inner = re.sub(r"^<p>|</p>$", "", inner.strip())  # keep prov spans inline
        span = f'<span class="prov" data-id="{html.escape(prov_id)}">{inner}</span>'
        body = body.replace(_PROV_TOKEN.format(idx), span)
    return body, [pid for pid, _ in refs]


def detect_format(path: str) -> str:
    """Guess the document format from a filename extension."""
    return "markdown" if str(path).lower().endswith((".md", ".markdown")) else "latex"
