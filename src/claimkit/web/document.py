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
from pathlib import Path

_INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
_DOC_BODY_RE = re.compile(r"\\begin\{document\}(.*)\\end\{document\}", re.DOTALL)
_MAX_INPUT_DEPTH = 15  # recursion guard for \input/\include expansion


def expand_inputs(path: str | Path, _depth: int = 0) -> str:
    r"""Read a LaTeX file, inlining ``\input``/``\include`` recursively.

    Paths resolve relative to the including file; a missing ``.tex`` suffix is
    added; unresolved includes are dropped. Recursion is capped to guard against
    cycles.

    Args:
        path: The LaTeX file to read and expand.
        _depth: Internal recursion guard.

    Returns:
        The file text with all resolvable includes inlined.
    """
    path = Path(path)
    text = path.read_text()
    if _depth >= _MAX_INPUT_DEPTH:
        return text

    def _sub(m: re.Match) -> str:
        target = path.parent / m.group(1).strip()
        if not target.suffix:
            target = target.with_suffix(".tex")
        return expand_inputs(target, _depth + 1) if target.exists() else ""

    return _INPUT_RE.sub(_sub, text)


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
_LATEX_DROP_ARG = re.compile(r"\\(?:label|cite[a-z]*|footnote|index)\s*\{[^{}]*\}")
_REF_RE = re.compile(r"\\(ref|eqref|cref|Cref|autoref)\s*\{([^}]+)\}")
#: \newlabel{KEY}{{NUMBER}{PAGE}...} in a LaTeX .aux; NUMBER has no nested braces.
_AUX_LABEL_RE = re.compile(r"\\newlabel\s*\{([^}]+)\}\s*\{\{([^{}]*)\}")
_FIGURE_RE = re.compile(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", re.DOTALL)
_INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\s*\{([^}]+)\}")
#: Image extensions a browser can show with <img>; a .pdf figure is embedded.
_RASTER_EXTS = (".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp")


def parse_aux_labels(aux_path: str | Path) -> dict[str, str]:
    r"""Parse ``\newlabel`` entries from a LaTeX ``.aux`` into ``{key: number}``.

    Args:
        aux_path: Path to the ``.aux`` file (may not exist).

    Returns:
        A mapping of label key to its printed number (e.g. ``sec:methods`` ->
        ``II``); empty if the file is absent.
    """
    aux_path = Path(aux_path)
    if not aux_path.exists():
        return {}
    labels: dict[str, str] = {}
    for key, num in _AUX_LABEL_RE.findall(aux_path.read_text(errors="replace")):
        if "@" in key:  # cleveref/hyperref sidecar labels
            continue
        clean = num.replace("\\,", " ").replace("\\;", " ").replace("{", "").replace("}", "").strip()
        if clean:
            labels[key] = clean
    return labels


def _resolve_refs(text: str, labels: dict[str, str]) -> str:
    r"""Replace ``\ref``/``\eqref``/``\cref`` with numbers from the aux labels."""

    def _sub(m: re.Match) -> str:
        cmd, key = m.group(1), m.group(2).strip()
        num = labels.get(key, "??")
        return f"({num})" if cmd == "eqref" else num

    return _REF_RE.sub(_sub, text)


#: Title-block commands whose (balanced-brace) argument is dropped entirely.
_DROP_CMDS = ("author", "email", "affiliation", "altaffiliation", "thanks", "homepage", "orcidlink", "date")
_DROP_CMDS_RE = re.compile(r"\\(?:" + "|".join(_DROP_CMDS) + r")\s*(?:\[[^\]]*\])?\s*(?=\{)")
# AMS/TeX math environments MathJax renders on its own — protect them verbatim
# from the prose macro-stripping. Backref \1 pairs the matching \end{...}.
_MATH_ENV_RE = re.compile(
    r"\\begin\{(equation\*?|align\*?|alignat\*?|gather\*?|multline\*?|eqnarray\*?|displaymath|math|split|cases|aligned)\}"  # typos:disable-line
    r".*?\\end\{\1\}",
    re.DOTALL,
)
_MATH_DISPLAY_RE = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]", re.DOTALL)
_MATH_INLINE_RE = re.compile(r"\$[^$\n]+?\$|\\\(.+?\\\)", re.DOTALL)


def _drop_cmds(text: str) -> str:
    r"""Drop title-block commands (``\author{...}`` etc.) with their arguments."""
    out = []
    i = 0
    while True:
        m = _DROP_CMDS_RE.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i : m.start()])
        _, end = _match_braces(text, m.end())
        i = end
    return "".join(out)


def _resolve_asset(raw: str, base: Path | None) -> tuple[str, str]:
    """Resolve an includegraphics path to a file; return (relpath, kind).

    ``kind`` is ``"img"`` (browser-renderable raster), ``"embed"`` (a PDF to
    embed), or ``"none"`` (no file found). A missing extension is resolved by
    trying raster extensions first, then ``.pdf``.
    """
    p = Path(raw)
    candidates = [p] if p.suffix else [p.with_suffix(e) for e in (*_RASTER_EXTS, ".pdf")]
    for c in candidates:
        if base is not None and (base / c).exists():
            return str(c), ("img" if c.suffix.lower() in _RASTER_EXTS else "embed")
    ext = p.suffix.lower()
    kind = "img" if ext in _RASTER_EXTS else "embed" if ext == ".pdf" else "none"
    return raw, kind


def _render_figure(block: str, labels: dict[str, str], base: Path | None, asset_prefix: str) -> str:
    """Render a LaTeX ``figure`` environment to an HTML ``<figure>``."""
    m = _INCLUDEGRAPHICS_RE.search(block)
    if m:
        rel, kind = _resolve_asset(m.group(1).strip(), base)
        src = html.escape(asset_prefix + rel)
        if kind == "img":
            inner = f'<img class="figimg" src="{src}" alt="figure"/>'
        elif kind == "embed":
            inner = f'<embed class="figpdf" src="{src}" type="application/pdf"/>'
        else:
            inner = f'<div class="fignote">[figure: {html.escape(m.group(1).strip())} — no renderable file]</div>'
    else:
        inner = '<div class="fignote">[figure pending]</div>'
    caption = ""
    cm = re.search(r"\\caption\s*\{", block)
    if cm:
        ctext, _ = _match_braces(block, cm.end() - 1)
        rendered = re.sub(r"^<p>|</p>$", "", _latex_prose_to_html(ctext, labels, base, asset_prefix).strip())
        caption = f"<figcaption>{rendered}</figcaption>"
    return f"<figure>{inner}{caption}</figure>"


def _latex_prose_to_html(
    text: str, labels: dict[str, str] | None = None, base: Path | None = None, asset_prefix: str = "/asset/"
) -> str:
    """Very small LaTeX->HTML prose pass; math is preserved for MathJax."""
    labels = labels or {}
    text = re.sub(r"(?<!\\)%.*", "", text)  # comments
    text = _resolve_refs(text, labels)
    # Figures -> HTML tokens, restored raw at the end (kept out of escaping).
    figures: list[str] = []

    def _keep_fig(mo: re.Match) -> str:
        figures.append(_render_figure(mo.group(0), labels, base, asset_prefix))
        return f"\x00F{len(figures) - 1}\x00"

    text = _FIGURE_RE.sub(_keep_fig, text)
    # Protect math (display before inline) so macro-stripping leaves it intact;
    # MathJax typesets it client-side. Escaped for HTML at restore time.
    math: list[str] = []

    def _keep_math(mo: re.Match) -> str:
        math.append(mo.group(0))
        return f"\x00M{len(math) - 1}\x00"

    text = _MATH_ENV_RE.sub(_keep_math, text)
    text = _MATH_DISPLAY_RE.sub(_keep_math, text)
    text = _MATH_INLINE_RE.sub(_keep_math, text)

    text = _drop_cmds(text)
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
    for cmd, tag in (("title", "h1"), ("section", "h2"), ("subsection", "h3"), ("subsubsection", "h4")):
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
    out_html = "\n".join(rendered)
    for idx, expr in enumerate(math):  # restore math verbatim (HTML-escaped, delimiters kept)
        out_html = out_html.replace(f"\x00M{idx}\x00", html.escape(expr))
    for idx, fig in enumerate(figures):  # restore figure HTML raw
        out_html = out_html.replace(f"\x00F{idx}\x00", fig)
    return out_html


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


def render_document(
    text: str, fmt: str, labels: dict[str, str] | None = None, base: Path | None = None
) -> tuple[str, list[str]]:
    r"""Render a draft to reading-view HTML with provenance spans.

    Args:
        text: The raw LaTeX or Markdown source.
        fmt: ``"latex"`` or ``"markdown"``.
        labels: ``{key: number}`` from the ``.aux`` for resolving ``\ref`` (LaTeX).
        base: Directory that ``\includegraphics`` paths resolve against (LaTeX).

    Returns:
        ``(html, ref_ids)`` — the rendered HTML and the provenance ids referenced
        (in document order, duplicates kept).
    """
    if fmt == "latex":
        body_match = _DOC_BODY_RE.search(text)
        if body_match:  # skip the preamble when given a full document
            text = body_match.group(1)
        stripped, refs = _extract_latex_prov(text)
        body = _latex_prose_to_html(stripped, labels, base)

        def inner_render(t: str) -> str:
            return _latex_prose_to_html(t, labels, base)
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
