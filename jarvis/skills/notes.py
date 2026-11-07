import re

NAME = "notes"
PATTERNS = [
    r"^(سجل|اكتب|اضف|ضيف)\s+(ملاحظه|مهمه)",
    r"^(ذكرني|ذكرني ان|ذكرني ب)\s+",
    r"^(note|add (a )?note|add (a )?task|remind me)\b",
    r"^(ملاحظاتي|مهامي|اعرض الملاحظات|my notes|my tasks|show notes|list notes)$",
    r"^(خلصت|انجزت|احذف|done|finish|delete)\s+(ملاحظه|مهمه|note|task)?\s*\d+$",
]
TESTS = ["سجل ملاحظة اختبار", "my notes", "done note 999"]


def handle(text, match, jarvis):
    mem = jarvis.memory
    t = text.strip()
    done = re.match(r"^(?:خلصت|انجزت|احذف|done|finish|delete)\s+(?:\S+\s+)?(\d+)$", t, re.IGNORECASE)
    if done:
        n = int(done.group(1))
        if mem.done_note(n):
            return jarvis.say(f"تم، شطبت الملاحظة رقم {n}.", f"Done. Note {n} is checked off.", text)
        return jarvis.say(f"ما لقيت ملاحظة رقم {n}.", f"I couldn't find note {n}.", text)

    if re.match(r"^(ملاحظاتي|مهامي|اعرض الملاحظات|my notes|my tasks|show notes|list notes)$", t, re.IGNORECASE):
        items = mem.notes()
        if not items:
            return jarvis.say("ما عندك ملاحظات حالياً.", "You have no notes.", text)
        lines = "\n".join(f"  {r['id']}. {r['text']}" for r in items)
        return jarvis.say(f"ملاحظاتك:\n{lines}", f"Your notes:\n{lines}", text)

    body = re.sub(r"^(?:سجل|اكتب|أضف|اضف|ضيف)\s+(?:ملاحظة|ملاحظه|مهمة|مهمه)\s*[:：]?\s*|"
                  r"^ذكرني\s+(?:ان|أن|ب)?\s*|^(?:note|add (?:a )?note|add (?:a )?task|remind me(?: to)?)\s*[:：]?\s*",
                  "", t, flags=re.IGNORECASE).strip()
    if not body:
        return jarvis.say("وش تبيني أسجل؟", "What should I write down?", text)
    n = mem.add_note(body)
    return jarvis.say(f"سجلتها برقم {n}: {body}", f"Noted as #{n}: {body}", text)
