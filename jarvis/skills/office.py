"""Make PowerPoint presentations and Word documents.

Examples:
  اعمل عرض تقديمي عن الذكاء الاصطناعي
  سوي بوربوينت عن الطاقة المتجددة 8 شرائح
  اعمل عرض عن مشروعي: الفكرة، السوق، الخطة، الميزانية
  اكتب تقرير وورد عن السلامة في المصانع
  make a presentation about climate change
  write a word document about time management
"""
import re

from jarvis.office import DOC_WORDS, PPT_WORDS, VERBS, make_document, make_presentation

NAME = "office"
PATTERNS = [
    rf"^{VERBS}\s+(?:لي\s+|me\s+)?(?:an?\s+)?(?:\S+\s+)?{PPT_WORDS}\b",
    rf"^{VERBS}\s+(?:لي\s+|me\s+)?(?:an?\s+)?(?:\S+\s+)?{DOC_WORDS}\b",
    rf"^{PPT_WORDS}\s+(?:عن|حول|about|on)\s+",
    rf"^{DOC_WORDS}\s+(?:عن|حول|about|on)\s+",
]
TESTS = []   # creating files is covered by the unit tests and --selftest


def handle(text, match, jarvis):
    is_ppt = re.search(PPT_WORDS, match.group(0), re.I) and not re.search(
        r"(وورد|word|docx|مستند|document)", match.group(0), re.I)
    maker = make_presentation if is_ppt else make_document
    path, source, outline = maker(jarvis, text)

    kind_ar, kind_en = ("العرض التقديمي", "presentation") if is_ppt else ("مستند الوورد", "Word document")
    count = len(outline["slides"]) + 2 if is_ppt else len(outline["sections"])
    unit_ar = ("شرائح" if 3 <= count <= 10 else "شريحة") if is_ppt else ("أقسام" if 3 <= count <= 10 else "قسم")
    unit_en = "slides" if is_ppt else "sections"
    note_ar = {
        "ai": "كتبت المحتوى بالذكاء الاصطناعي.",
        "points": "بنيته من النقاط اللي أعطيتني.",
        "template": "ما فيه عقل ذكاء اصطناعي متصل الحين، فجهزت لك هيكل جاهز تعبّيه "
                    "(شغّل Ollama أو أضف مفتاح Claude عشان أكتب المحتوى بنفسي).",
    }[source]
    note_en = {
        "ai": "Content written by AI.",
        "points": "Built from the points you gave me.",
        "template": "No AI brain is connected right now, so this is a ready-to-fill skeleton "
                    "(run Ollama or add a Claude key and I'll write the content).",
    }[source]
    return jarvis.say(
        f"✅ جهزت {kind_ar} «{outline['title']}» ({count} {unit_ar}).\n{note_ar}\n📁 {path}",
        f"✅ Your {kind_en} \"{outline['title']}\" is ready ({count} {unit_en}).\n{note_en}\n📁 {path}",
        text)
