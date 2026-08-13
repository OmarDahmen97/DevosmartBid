# file: app/generation/pptx_renderer/template_filler.py
"""
Fills the DVT PPTX template (Templates/Template_CV_format_DVT.pptx) from a
cv_json produced by cv_json_builder.build_cv_json_from_selection.

Shape IDs below were identified by inspecting the template's raw slide XML
(ppt/slides/slide1.xml, slide2.xml) -- they are specific to this template file
and will break if the template's shapes are re-authored (id changes, shapes
deleted/reordered). If the template changes, re-run the inspection in
xml_helpers-adjacent scratch code and update SLIDE1_SHAPES/SLIDE2_SHAPES.
"""

import shutil
import zipfile
from pathlib import Path

from lxml import etree

from .xml_helpers import (
    _make_run, qn, NS, find_shape_by_id, get_txBody, remove_shape, remove_shape, set_single_run_text,
    make_bold_paragraph, make_bullet_paragraph, make_spacer_paragraph,
    clear_paragraphs,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = PROJECT_ROOT / "Templates" / "Template_CV_format_DVT.pptx"

SLIDE1_SHAPES = {
    "name": "869", "summary": "870", "years": "872", "title": "877",
    "education": "879", "skills": "881", "exp1": "882", "exp2": "887",
}
SLIDE2_SHAPES = {
    "name": "11", "title": "15", "exp_box_a": "3", "exp_box_b": "5",
}

# Pagination heuristic (agreed approach): first 2 experiences go on slide 1's
# fixed slots; the rest are split across slide 2's two text boxes, capped at
# this many per box per page -- beyond that we duplicate slide 2 for a new
# page rather than risk uncontrolled text overflow. No text-measurement API
# is used here, so this is a conservative estimate, not a guarantee against
# overflow on very long descriptions -- visual QA on real output is still needed.
MAX_EXPERIENCES_PER_BOX = 3


def _experience_title_line(exp: dict) -> str:
    company = exp.get("company") or ""
    title = exp.get("title") or ""
    if company and title:
        return f"{company} | {title} :"
    return company or title or ""


def _experience_bullets(exp: dict) -> list[str]:
    bullets = []
    responsibilities = exp.get("responsibilities") or []
    if responsibilities:
        for r in responsibilities:
            text = (r.get("description") or r.get("category") or "").strip()
            if text:
                bullets.append(text)
    elif exp.get("description"):
        # No structured responsibilities -- fall back to the free-text
        # description as a single bullet rather than fabricating a split.
        bullets.append(exp["description"].strip())
    return bullets


def fill_single_experience_shape(sp, exp: dict) -> None:
    """Fills a slide-1-style shape meant to hold exactly ONE experience."""
    txBody = get_txBody(sp)
    clear_paragraphs(txBody)
    txBody.append(make_spacer_paragraph())
    txBody.append(make_bold_paragraph(_experience_title_line(exp)))
    for bullet_text in _experience_bullets(exp):
        txBody.append(make_bullet_paragraph(bullet_text))


def fill_multi_experience_shape(sp, experiences: list[dict]) -> None:
    """Fills a slide-2-style box meant to hold SEVERAL experiences stacked
    as consecutive title+bullets blocks (matches the template's own pattern,
    e.g. shape id=3 originally held BNP Paribas + UBCI)."""
    txBody = get_txBody(sp)
    clear_paragraphs(txBody)
    for exp in experiences:
        txBody.append(make_bold_paragraph(_experience_title_line(exp)))
        for bullet_text in _experience_bullets(exp):
            txBody.append(make_bullet_paragraph(bullet_text))


def fill_skills_shape(sp, skills: list[str]) -> None:
    """Skills rendered as one flowing line ('Python  •  SQL  •  RAG  •  ...')
    instead of one bullet per skill -- a per-item bullet list overflows this
    box past ~10 skills and collides with the sections below it."""
    txBody = get_txBody(sp)
    clear_paragraphs(txBody)
    clean = [str(s) for s in skills if s]
    p = etree.Element(qn("a:p"))
    p.append(_make_run("  •  ".join(clean), size=800, bold=False))
    txBody.append(p)


def fill_education_shape(sp, education: list[dict]) -> None:
    txBody = get_txBody(sp)
    clear_paragraphs(txBody)
    if not education:
        txBody.append(make_bold_paragraph(""))
        return
    for edu in education:
        parts = [p for p in (
            edu.get("degree"),
            edu.get("field_of_study"),
            edu.get("institution"),
        ) if p]
        line = " - ".join(parts)
        years = edu.get("years")
        if years:
            line = f"{line} ({years})" if line else str(years)
        if line:
            txBody.append(make_bold_paragraph(line, size=750))


def fill_slide1(root, cv_json: dict) -> None:
    spTree = root.find(f".//{qn('p:cSld')}/{qn('p:spTree')}")

    name_sp = find_shape_by_id(spTree, SLIDE1_SHAPES["name"])
    set_single_run_text(name_sp, cv_json.get("name") or "")

    title_sp = find_shape_by_id(spTree, SLIDE1_SHAPES["title"])
    set_single_run_text(title_sp, cv_json.get("title") or "")

    years = cv_json.get("years_of_experience")
    years_sp = find_shape_by_id(spTree, SLIDE1_SHAPES["years"])
    set_single_run_text(years_sp, f"{years} ans d’expérience" if years else "")

    summary_sp = find_shape_by_id(spTree, SLIDE1_SHAPES["summary"])
    set_single_run_text(summary_sp, cv_json.get("summary") or "")

    education_sp = find_shape_by_id(spTree, SLIDE1_SHAPES["education"])
    fill_education_shape(education_sp, cv_json.get("education") or [])

    skills_sp = find_shape_by_id(spTree, SLIDE1_SHAPES["skills"])
    fill_skills_shape(skills_sp, cv_json.get("skills") or [])

    experiences = cv_json.get("experience") or []
    exp1_sp = find_shape_by_id(spTree, SLIDE1_SHAPES["exp1"])
    exp2_sp = find_shape_by_id(spTree, SLIDE1_SHAPES["exp2"])
    fill_single_experience_shape(exp1_sp, experiences[0] if len(experiences) > 0 else {})
    fill_single_experience_shape(exp2_sp, experiences[1] if len(experiences) > 1 else {})


def fill_slide2_header(root, cv_json: dict) -> None:
    spTree = root.find(f".//{qn('p:cSld')}/{qn('p:spTree')}")
    name_sp = find_shape_by_id(spTree, SLIDE2_SHAPES["name"])
    set_single_run_text(name_sp, cv_json.get("name") or "")
    title_sp = find_shape_by_id(spTree, SLIDE2_SHAPES["title"])
    set_single_run_text(title_sp, cv_json.get("title") or "")


def fill_slide2_experiences(root, experiences_page: list[dict]) -> None:
    spTree = root.find(f".//{qn('p:cSld')}/{qn('p:spTree')}")
    box_a = find_shape_by_id(spTree, SLIDE2_SHAPES["exp_box_a"])
    box_b = find_shape_by_id(spTree, SLIDE2_SHAPES["exp_box_b"])
    split = MAX_EXPERIENCES_PER_BOX
    fill_multi_experience_shape(box_a, experiences_page[:split])
    fill_multi_experience_shape(box_b, experiences_page[split:split * 2])


def _next_free_slide_number(slides_dir: Path) -> int:
    existing = [int(p.stem.replace("slide", "")) for p in slides_dir.glob("slide[0-9]*.xml")]
    return max(existing) + 1


def duplicate_slide2(workdir: Path) -> Path:
    """
    Duplicates ppt/slides/slide2.xml as a new page, doing every registration
    step a new slide needs: copy the XML + rels, declare it in
    [Content_Types].xml, add a relationship + <p:sldId> in presentation.xml.
    Returns the path to the new slide XML for further content editing.
    """
    slides_dir = workdir / "ppt" / "slides"
    new_num = _next_free_slide_number(slides_dir)
    new_slide_path = slides_dir / f"slide{new_num}.xml"
    shutil.copy(slides_dir / "slide2.xml", new_slide_path)
    shutil.copy(
        slides_dir / "_rels" / "slide2.xml.rels",
        slides_dir / "_rels" / f"slide{new_num}.xml.rels",
    )

    # [Content_Types].xml
    ct_path = workdir / "[Content_Types].xml"
    ct_tree = etree.parse(str(ct_path))
    ct_root = ct_tree.getroot()
    ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    override = etree.SubElement(ct_root, f"{{{ct_ns}}}Override")
    override.set("PartName", f"/ppt/slides/slide{new_num}.xml")
    override.set(
        "ContentType",
        "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
    )
    ct_tree.write(str(ct_path), xml_declaration=True, encoding="UTF-8", standalone=True)

    # ppt/_rels/presentation.xml.rels
    pres_rels_path = workdir / "ppt" / "_rels" / "presentation.xml.rels"
    rels_tree = etree.parse(str(pres_rels_path))
    rels_root = rels_tree.getroot()
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    existing_ids = [r.get("Id") for r in rels_root]
    next_rid_num = max(int(rid.replace("rId", "")) for rid in existing_ids) + 1
    new_rid = f"rId{next_rid_num}"
    new_rel = etree.SubElement(rels_root, f"{{{rel_ns}}}Relationship")
    new_rel.set("Id", new_rid)
    new_rel.set(
        "Type",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
    )
    new_rel.set("Target", f"slides/slide{new_num}.xml")
    rels_tree.write(str(pres_rels_path), xml_declaration=True, encoding="UTF-8", standalone=True)

    # ppt/presentation.xml -- add <p:sldId> at the end of sldIdLst
    pres_path = workdir / "ppt" / "presentation.xml"
    pres_tree = etree.parse(str(pres_path))
    pres_root = pres_tree.getroot()
    sldIdLst = pres_root.find(qn("p:sldIdLst"))
    existing_slide_ids = [int(s.get("id")) for s in sldIdLst]
    new_slide_id = max(existing_slide_ids) + 1
    new_sldId = etree.SubElement(sldIdLst, qn("p:sldId"))
    new_sldId.set("id", str(new_slide_id))
    new_sldId.set(f"{{{NS['r']}}}id", new_rid)
    pres_tree.write(str(pres_path), xml_declaration=True, encoding="UTF-8", standalone=True)

    return new_slide_path


def render_cv_pptx(cv_json: dict, output_path: str) -> str:
    workdir = Path("/tmp") / f"pptx_render_{id(cv_json)}"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    with zipfile.ZipFile(TEMPLATE_PATH) as z:
        z.extractall(workdir)

    slides_dir = workdir / "ppt" / "slides"
    parser = etree.XMLParser(remove_blank_text=False)

    # --- Slide 1 ---
    slide1_tree = etree.parse(str(slides_dir / "slide1.xml"), parser)
    fill_slide1(slide1_tree.getroot(), cv_json)
    spTree1 = slide1_tree.getroot().find(f".//{qn('p:cSld')}/{qn('p:spTree')}")
    remove_shape(spTree1, "2")
    slide1_tree.write(str(slides_dir / "slide1.xml"), xml_declaration=True, encoding="UTF-8", standalone=True)

    # --- Slide 2 + overflow pages ---
    experiences = cv_json.get("experience") or []
    remaining = experiences[2:]  # first 2 already placed on slide 1
    per_page = MAX_EXPERIENCES_PER_BOX * 2
    pages = [remaining[i:i + per_page] for i in range(0, len(remaining), per_page)] or [[]]

    slide2_tree = etree.parse(str(slides_dir / "slide2.xml"), parser)
    fill_slide2_header(slide2_tree.getroot(), cv_json)
    spTree2 = slide2_tree.getroot().find(f".//{qn('p:cSld')}/{qn('p:spTree')}")
    remove_shape(spTree2, "16")
    fill_slide2_experiences(slide2_tree.getroot(), pages[0])
    slide2_tree.write(str(slides_dir / "slide2.xml"), xml_declaration=True, encoding="UTF-8", standalone=True)

    for extra_page in pages[1:]:
        new_slide_path = duplicate_slide2(workdir)
        page_tree = etree.parse(str(new_slide_path), parser)
        fill_slide2_header(page_tree.getroot(), cv_json)
        fill_slide2_experiences(page_tree.getroot(), extra_page)
        page_tree.write(str(new_slide_path), xml_declaration=True, encoding="UTF-8", standalone=True)

    # --- Repack ---
    output_path = str(output_path)
    if Path(output_path).exists():
        Path(output_path).unlink()
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in workdir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(workdir))

    shutil.rmtree(workdir)
    return output_path