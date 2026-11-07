"""PowerPoint presentations and Word documents (Arabic right-to-left supported).

Content comes from an AI brain (Claude/Ollama) when one is available. Without
one, Jarvis still builds a clean file: from the points you give it
("اعمل عرض عن الطاقة: الشمس، الرياح، الماء") or a ready-to-fill skeleton.

Needs `python-pptx` and `python-docx` (bundled in Jarvis.exe; on a plain
Python install the self-healer installs them the first time they're needed).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from .text import is_arabic

NAVY, CYAN, ICE, INK, MUTED_HEX, PAPER = "0B1422", "3FD0FF", "D8F3FF", "1A2433", "6B8AA3", "F4F7FB"
FONT = "Segoe UI"

# ------------------------------------------------------------------ outline
VERBS = r"(?:اعمل|اعمللي|سو|سوي|سويلي|جهز|جهزلي|انشئ|انشي|اكتب|اكتبلي|حضر|حضرلي|صمم|ابغى|ابي|اريد|make|create|build|prepare|generate|write|design|draft)"
PPT_WORDS = r"(?:عرض\s+تقديمي|عرض\s+بوربوينت|عرض\s+باوربوينت|بوربوينت|باوربوينت|شرائح|عرض|presentation|powerpoint|slides|slide\s+deck|deck|pptx)"
DOC_WORDS = r"(?:ملف\s+وورد|مستند\s+وورد|وورد|مستند|تقرير|مقال|بحث|خطاب|رساله|word\s+document|word\s+file|word|document|report|article|essay|letter|docx)"


def extract_topic(text: str) -> tuple[str, list[str]]:
    """'اعمل عرض عن الطاقة: شمس، رياح' -> ('الطاقة', ['شمس', 'رياح'])."""
    t = text.strip().rstrip("؟?.!")
    points: list[str] = []
    if ":" in t or "：" in t:
        t, rest = re.split(r"[:：]", t, maxsplit=1)
        points = [p.strip(" -•\t") for p in re.split(r"[،,\n؛;]|\s+-\s+", rest) if p.strip(" -•\t")]
    m = re.search(r"(?:\bعن\b|\bحول\b|بعنوان|موضوعه|\babout\b|\bon\b|\btitled\b|\bcalled\b)\s+(.+)$", t, re.I)
    if m:
        topic = m.group(1)
    else:
        topic = re.sub(rf"^\s*{VERBS}\s+(?:لي\s+|me\s+)?(?:an?\s+)?", "", t, flags=re.I)
        topic = re.sub(rf"^\s*(?:{PPT_WORDS}|{DOC_WORDS})\s*", "", topic, flags=re.I)
    topic = re.sub(r"\s*(?:في|من|بـ?)?\s*\d+\s*(?:شرائح|شريحه|شريحة|slides?|صفحات|pages?)\s*", " ", topic, flags=re.I)
    topic = topic.strip(" \"'«»") or text.strip()
    if not is_arabic(topic):
        topic = topic[:1].upper() + topic[1:]
    return topic, points


def wanted_count(text: str, default: int) -> int:
    m = re.search(r"(\d+)\s*(?:شرائح|شريحه|شريحة|slides?|اقسام|أقسام|sections?)", text, re.I)
    return max(3, min(20, int(m.group(1)))) if m else default


def _ask_json(jarvis, prompt: str) -> dict | None:
    from .brains import BrainError
    try:
        reply, _ = jarvis.router.ask([{"role": "user", "content": prompt}],
                                     system="You produce clean JSON only, no prose, no code fences.", llm_only=True)
    except BrainError:
        return None
    m = re.search(r"\{.*\}", reply, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def presentation_outline(jarvis, request: str) -> tuple[dict, str]:
    """Returns (outline, source) where source is 'ai', 'points' or 'template'."""
    topic, points = extract_topic(request)
    ar = is_arabic(request)
    n = wanted_count(request, len(points) + 2 if points else 7)
    if not points:
        lang = "Arabic" if ar else "English"
        data = _ask_json(jarvis, (
            f"Create a presentation outline in {lang} about: {topic}\n"
            f"Original request: {request}\n"
            f"Return JSON: {{\"title\": str, \"subtitle\": str, \"slides\": [{{\"title\": str, "
            f"\"bullets\": [3-5 short strings], \"notes\": str}}]}} with exactly {n} content slides. "
            "Bullets must be concise (max ~12 words), factual and specific."))
        if _valid_outline(data):
            return data, "ai"
    if points:
        hint = "أضف التفاصيل هنا …" if ar else "Add details here …"
        slides = [{"title": p, "bullets": [hint, hint], "notes": ""} for p in points]
        intro = {"title": "مقدمة" if ar else "Introduction",
                 "bullets": [f"{'نظرة عامة على' if ar else 'Overview of'} {topic}"] +
                            [p for p in points[:4]], "notes": ""}
        return {"title": topic, "subtitle": "", "slides": [intro] + slides}, "points"
    if ar:
        sections = ["مقدمة", "الأهداف", "الفكرة الرئيسية", "التفاصيل", "أمثلة", "التحديات والحلول", "الخلاصة"]
        hint = "اكتب هنا"
    else:
        sections = ["Introduction", "Goals", "Main idea", "Details", "Examples", "Challenges & solutions", "Conclusion"]
        hint = "Add your point here"
    slides = [{"title": s, "bullets": [f"{hint} …"] * 3, "notes": ""} for s in sections[:n]]
    return {"title": topic, "subtitle": "", "slides": slides}, "template"


def document_outline(jarvis, request: str) -> tuple[dict, str]:
    topic, points = extract_topic(request)
    ar = is_arabic(request)
    if not points:
        lang = "Arabic" if ar else "English"
        n = wanted_count(request, 5)
        data = _ask_json(jarvis, (
            f"Write a well-structured document in {lang} about: {topic}\n"
            f"Original request: {request}\n"
            f"Return JSON: {{\"title\": str, \"sections\": [{{\"heading\": str, \"paragraphs\": [1-3 strings], "
            f"\"bullets\": [0-5 strings]}}]}} with about {n} sections. Write full, informative paragraphs."))
        if _valid_document(data):
            return data, "ai"
    if points:
        para = "اكتب هنا …" if ar else "Write here …"
        return {"title": topic, "sections": [{"heading": p, "paragraphs": [para], "bullets": []}
                                             for p in points]}, "points"
    if ar:
        heads = ["مقدمة", "الموضوع الرئيسي", "التفاصيل", "الخلاصة"]
        para = "اكتب هنا …"
    else:
        heads = ["Introduction", "Main topic", "Details", "Conclusion"]
        para = "Write here …"
    return {"title": topic, "sections": [{"heading": h, "paragraphs": [para], "bullets": []} for h in heads]}, "template"


def _strs(x) -> list[str]:
    return [str(i).strip() for i in x if str(i).strip()] if isinstance(x, list) else []


def _valid_outline(d) -> bool:
    if not isinstance(d, dict) or not isinstance(d.get("slides"), list) or not d["slides"]:
        return False
    d["title"] = str(d.get("title") or "").strip() or "Presentation"
    d["subtitle"] = str(d.get("subtitle") or "").strip()
    d["slides"] = [{"title": str(s.get("title", "")).strip(), "bullets": _strs(s.get("bullets")),
                    "notes": str(s.get("notes") or "")} for s in d["slides"] if isinstance(s, dict)]
    return bool(d["slides"])


def _valid_document(d) -> bool:
    if not isinstance(d, dict) or not isinstance(d.get("sections"), list) or not d["sections"]:
        return False
    d["title"] = str(d.get("title") or "").strip() or "Document"
    d["sections"] = [{"heading": str(s.get("heading", "")).strip(), "paragraphs": _strs(s.get("paragraphs")),
                      "bullets": _strs(s.get("bullets"))} for s in d["sections"] if isinstance(s, dict)]
    return bool(d["sections"])


# ------------------------------------------------------------------ files
def safe_name(title: str, ext: str, folder: Path) -> Path:
    stem = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip()
    stem = re.sub(r"\s+", " ", stem)[:60] or "jarvis"
    path = folder / f"{stem}{ext}"
    i = 2
    while path.exists():
        path = folder / f"{stem} ({i}){ext}"
        i += 1
    return path


def open_file(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


# ------------------------------------------------------------------ PowerPoint
def _rgb(hex_):
    from pptx.dml.color import RGBColor
    return RGBColor.from_string(hex_)


def _set_rtl(paragraph, rtl: bool):
    from pptx.enum.text import PP_ALIGN
    paragraph.alignment = PP_ALIGN.RIGHT if rtl else PP_ALIGN.LEFT
    if rtl:
        paragraph._p.get_or_add_pPr().set("rtl", "1")


def _style_run(run, size, color, bold=False):
    from pptx.oxml.ns import qn
    from pptx.util import Pt
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)
    run.font.name = FONT
    # Arabic text uses the complex-script font slot. Schema order is latin, ea, cs.
    latin = run._r.get_or_add_rPr().get_or_add_latin()
    prev = latin
    for tag in ("a:ea", "a:cs"):
        el = latin.getparent().find(qn(tag))
        if el is None:
            el = latin.makeelement(qn(tag), {})
            prev.addnext(el)
        el.set("typeface", FONT)
        prev = el
    return run


def _text(slide, x, y, w, h, text, size, color, bold=False, rtl=False, center=False):
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE if center else MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    _set_rtl(p, rtl)
    if center:
        p.alignment = PP_ALIGN.CENTER
    _style_run(p.add_run(), size, color, bold).text = text
    return box


def _rect(slide, x, y, w, h, color):
    from pptx.enum.shapes import MSO_SHAPE
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(color)
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def _background(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(color)


def build_presentation(outline: dict, path: Path) -> Path:
    from pptx import Presentation
    from pptx.oxml.ns import qn
    from pptx.util import Emu, Inches, Pt

    rtl = is_arabic(outline["title"] + " ".join(s["title"] for s in outline["slides"]))
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    W, H = prs.slide_width, prs.slide_height
    blank = prs.slide_layouts[6]
    M = Inches(0.8)

    # title slide
    s = prs.slides.add_slide(blank)
    _background(s, NAVY)
    _rect(s, M, Inches(4.15), Inches(2.2), Emu(45720), CYAN) if not rtl else \
        _rect(s, W - M - Inches(2.2), Inches(4.15), Inches(2.2), Emu(45720), CYAN)
    _text(s, M, Inches(2.0), W - 2 * M, Inches(2.0), outline["title"], 44, "FFFFFF", True, rtl)
    sub = outline.get("subtitle") or date.today().strftime("%Y-%m-%d")
    _text(s, M, Inches(4.4), W - 2 * M, Inches(0.8), sub, 20, CYAN, False, rtl)

    # content slides
    for i, sl in enumerate(outline["slides"], start=1):
        s = prs.slides.add_slide(blank)
        _background(s, "FFFFFF")
        _rect(s, W - Inches(0.25) if rtl else 0, 0, Inches(0.25), H, NAVY)
        _rect(s, M, Inches(1.55), Inches(1.4), Emu(38100), CYAN) if not rtl else \
            _rect(s, W - M - Inches(1.4), Inches(1.55), Inches(1.4), Emu(38100), CYAN)
        _text(s, M, Inches(0.55), W - 2 * M, Inches(1.0), sl["title"], 32, NAVY, True, rtl)
        if sl["bullets"]:
            box = s.shapes.add_textbox(M, Inches(1.9), W - 2 * M, H - Inches(2.7))
            tf = box.text_frame
            tf.word_wrap = True
            for j, b in enumerate(sl["bullets"]):
                p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                _set_rtl(p, rtl)
                p.space_after = Pt(14)
                pPr = p._p.get_or_add_pPr()
                pPr.set("marL" if not rtl else "marR", str(Inches(0.35)))
                pPr.set("indent", str(-Inches(0.3)))
                bu_clr = pPr.makeelement(qn("a:buClr"), {})
                srgb = bu_clr.makeelement(qn("a:srgbClr"), {"val": CYAN})
                bu_clr.append(srgb)
                pPr.append(bu_clr)
                pPr.append(pPr.makeelement(qn("a:buChar"), {"char": "■"}))
                _style_run(p.add_run(), 22, INK).text = b
        _text(s, M, H - Inches(0.6), W - 2 * M, Inches(0.4), f"{i}", 11, MUTED_HEX, False, not rtl)
        if sl.get("notes"):
            s.notes_slide.notes_text_frame.text = sl["notes"]

    # closing slide
    s = prs.slides.add_slide(blank)
    _background(s, NAVY)
    _text(s, M, Inches(2.6), W - 2 * M, Inches(1.4), "شكراً لكم" if rtl else "Thank you", 48, "FFFFFF", True, rtl,
          center=True)
    _text(s, M, Inches(4.0), W - 2 * M, Inches(0.6), outline["title"], 18, CYAN, False, rtl, center=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))
    return path


# ------------------------------------------------------------------ Word
# Elements that must come AFTER w:bidi inside w:pPr / w:sectPr (ECMA-376 schema order).
_PPR_AFTER_BIDI = ("w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind", "w:contextualSpacing",
                   "w:mirrorIndents", "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment",
                   "w:textboxTightWrap", "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr",
                   "w:pPrChange")
_SECT_AFTER_BIDI = ("w:rtlGutter", "w:docGrid", "w:printerSettings", "w:sectPrChange")


def _docx_rtl(paragraph, rtl: bool):
    """Right-to-left paragraph. No explicit alignment: an RTL paragraph already starts at the right
    (setting 'right' would flip it to the left in Word's bidi rules)."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    if not rtl:
        return
    ppr = paragraph._p.get_or_add_pPr()
    if ppr.find(qn("w:bidi")) is None:
        ppr.insert_element_before(OxmlElement("w:bidi"), *_PPR_AFTER_BIDI)
    for run in paragraph.runs:
        run._r.get_or_add_rPr().get_or_add_rtl()


def _docx_fonts(doc):
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "List Bullet"):
        try:
            st = doc.styles[name]
        except KeyError:
            continue
        st.font.name = FONT
        rpr = st.element.get_or_add_rPr()
        fonts = rpr.get_or_add_rFonts()
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            fonts.set(qn(attr), FONT)
        if name == "Normal":
            st.font.size = Pt(12)
            sz = rpr.find(qn("w:sz"))
            if sz is not None and rpr.find(qn("w:szCs")) is None:   # w:szCs comes right after w:sz
                sz.addnext(rpr.makeelement(qn("w:szCs"), {qn("w:val"): "24"}))
        if name.startswith("Heading") or name == "Title":
            st.font.color.rgb = RGBColor.from_string(NAVY)


def build_document(outline: dict, path: Path) -> Path:
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.shared import Pt, RGBColor

    rtl = is_arabic(outline["title"] + " ".join(s["heading"] for s in outline["sections"]))
    doc = Document()
    _docx_fonts(doc)
    if rtl:
        doc.sections[0]._sectPr.insert_element_before(OxmlElement("w:bidi"), *_SECT_AFTER_BIDI)

    _docx_rtl(doc.add_heading(outline["title"], level=0), rtl)
    meta = doc.add_paragraph()
    r = meta.add_run(date.today().strftime("%Y-%m-%d"))
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor.from_string(MUTED_HEX)
    _docx_rtl(meta, rtl)

    for sec in outline["sections"]:
        if sec["heading"]:
            _docx_rtl(doc.add_heading(sec["heading"], level=1), rtl)
        for para in sec["paragraphs"]:
            p = doc.add_paragraph(para)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.3
            _docx_rtl(p, rtl)
        for b in sec["bullets"]:
            _docx_rtl(doc.add_paragraph(b, style="List Bullet"), rtl)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


# ------------------------------------------------------------------ entry points
def make_presentation(jarvis, request: str) -> tuple[Path, str, dict]:
    outline, source = presentation_outline(jarvis, request)
    path = safe_name(outline["title"], ".pptx", jarvis.config.outputs)
    build_presentation(outline, path)
    if jarvis.config["open_created_files"]:
        open_file(path)
    return path, source, outline


def make_document(jarvis, request: str) -> tuple[Path, str, dict]:
    outline, source = document_outline(jarvis, request)
    path = safe_name(outline["title"], ".docx", jarvis.config.outputs)
    build_document(outline, path)
    if jarvis.config["open_created_files"]:
        open_file(path)
    return path, source, outline
