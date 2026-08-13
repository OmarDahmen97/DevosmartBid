# file: app/generation/pptx_renderer/xml_helpers.py
"""
Low-level XML manipulation for the DVT CV template. Uses lxml.etree
(NOT xml.etree.ElementTree) because ElementTree rewrites namespace prefixes
on write, which corrupts OOXML parts that reference prefixed styles.
"""

from lxml import etree

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
A = NS["a"]
P = NS["p"]


def qn(tag: str) -> str:
    """'a:p' -> '{namespace}p'"""
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def find_shape_by_id(spTree, shape_id: str):
    """Find a <p:sp> (or <p:pic>) anywhere under spTree by its cNvPr id, including inside groups."""
    for sp in spTree.iter():
        if sp.tag not in (qn("p:sp"), qn("p:pic")):
            continue
        nv = sp.find(f".//{qn('p:cNvPr')}")
        if nv is not None and nv.get("id") == str(shape_id):
            return sp
    return None


def get_txBody(sp):
    return sp.find(f".//{qn('p:txBody')}")


def set_single_run_text(sp, text: str) -> None:
    """
    Replace the text of a shape that's meant to hold ONE simple run
    (name, title, years-of-experience label, education line, etc.).
    Keeps the first <a:r>'s <a:rPr> (font/size/bold) untouched, drops any
    extra paragraphs/runs beyond the first so leftover template content
    can't survive a shorter replacement value.
    """
    txBody = get_txBody(sp)
    paragraphs = txBody.findall(qn("a:p"))
    if not paragraphs:
        return
    first_p = paragraphs[0]
    for extra_p in paragraphs[1:]:
        txBody.remove(extra_p)

    runs = first_p.findall(qn("a:r"))
    if not runs:
        return
    first_run = runs[0]
    for extra_r in runs[1:]:
        first_p.remove(extra_r)

    t = first_run.find(qn("a:t"))
    if t is None:
        t = etree.SubElement(first_run, qn("a:t"))
    t.text = text or ""


def _make_run(text: str, size: int, bold: bool, font: str = "Montserrat"):
    r = etree.Element(qn("a:r"))
    rPr = etree.SubElement(r, qn("a:rPr"))
    rPr.set("lang", "fr-FR")
    rPr.set("sz", str(size))
    rPr.set("b", "1" if bold else "0")
    rPr.set("dirty", "0")
    latin = etree.SubElement(rPr, qn("a:latin"))
    latin.set("typeface", font)
    t = etree.SubElement(r, qn("a:t"))
    t.text = text
    return r


def make_bold_paragraph(text: str, size: int = 800) -> "etree._Element":
    """A plain (non-bulleted) bold paragraph -- used for experience titles."""
    p = etree.Element(qn("a:p"))
    p.append(_make_run(text, size, bold=True))
    return p


def make_bullet_paragraph(text: str, size: int = 800) -> "etree._Element":
    """A bulleted paragraph matching the template's bullet style (marL/indent + '•')."""
    p = etree.Element(qn("a:p"))
    pPr = etree.SubElement(p, qn("a:pPr"))
    pPr.set("marL", "128588")
    pPr.set("indent", "-128588")
    buFont = etree.SubElement(pPr, qn("a:buFont"))
    buFont.set("typeface", "Arial")
    buFont.set("panose", "020B0604020202020204")
    buFont.set("pitchFamily", "34")
    buFont.set("charset", "0")
    buChar = etree.SubElement(pPr, qn("a:buChar"))
    buChar.set("char", "•")
    p.append(_make_run(text, size, bold=False))
    return p


def make_spacer_paragraph(size: int = 825) -> "etree._Element":
    """Empty paragraph the template uses between experience blocks."""
    p = etree.Element(qn("a:p"))
    endParaRPr = etree.SubElement(p, qn("a:endParaRPr"))
    endParaRPr.set("lang", "fr-FR")
    endParaRPr.set("sz", str(size))
    endParaRPr.set("b", "1")
    endParaRPr.set("dirty", "0")
    return p


def clear_paragraphs(txBody) -> None:
    """Remove every <a:p> from a txBody, keeping <a:bodyPr>/<a:lstStyle>."""
    for p in txBody.findall(qn("a:p")):
        txBody.remove(p)

def remove_shape(spTree, shape_id: str) -> None:
    """Removes a shape (and its parent, if it's inside a group) from spTree by id."""
    for sp in spTree.iter():
        if sp.tag not in (qn("p:sp"), qn("p:pic")):
            continue
        nv = sp.find(f".//{qn('p:cNvPr')}")
        if nv is not None and nv.get("id") == str(shape_id):
            parent = sp.getparent()
            if parent is not None:
                parent.remove(sp)
            return  


def make_plain_paragraph(text: str, size: int = 800, bold: bool = False) -> "etree._Element":
    p = etree.Element(qn("a:p"))
    p.append(_make_run(text, size, bold))
    return p                  