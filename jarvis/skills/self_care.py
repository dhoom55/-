"""Commands about Jarvis itself: help, diagnostics, healing, what it has learned."""
import re

NAME = "self_care"
PATTERNS = [
    r"^(مساعده|ساعدني|وش تقدر تسوي|ايش تقدر تسوي|الاوامر|help|commands|what can you do)$",
    r"(افحص نفسك|فحص ذاتي|تشخيص|diagnose|self check|health check|run diagnostics)",
    r"(اصلح نفسك|صلح نفسك|عالج نفسك|heal yourself|fix yourself|repair yourself|self repair)",
    r"(وش تعلمت|ماذا تعلمت|ايش تعلمت|what have you learned|what did you learn|what do you know about me)",
    r"(حاله العقول|العقول|اي عقل|brains|brain status|which brain)",
    r"(الاعطال|الاخطاء|سجل الاخطاء|show errors|error log|recent errors)",
    r"(نسخه احتياطيه|اعمل نسخه|backup)",
    r"^(فعل|شغل|enable)\s+(مهاره|skill)\s+\S+",
    r"^(المهارات|مهاراتك|skills|list skills)$",
]
TESTS = ["help", "افحص نفسك", "وش تعلمت", "brains", "show errors", "skills"]

HELP_AR = """أقدر أساعدك في:
  • المحادثة والأسئلة (عن طريق Claude أو Ollama إذا كانوا متوفرين، أو من معرفتي المحلية)
  • الوقت والتاريخ: «كم الساعة؟»
  • الحساب: «احسب 15 * 4»
  • الملاحظات: «سجل ملاحظة ...» / «ملاحظاتي» / «خلصت ملاحظة 2»
  • حالة الجهاز: «حالة النظام»
الصوت 🎤:
  • زر الميكروفون للكلام، وزر السماعة للرد بالصوت   • «فعّل الصوت» / «اسكت»   • «قل ...»   • «اختبر الصوت»
البرمجة 👨‍💻:
  • «اكتب برنامج بايثون يحسب ...»   • «شغل الكود» (يصلح الأخطاء تلقائياً)   • «عدل الكود: ...»   • «وين الكود»
الذكاء الاصطناعي المحلي 🧠:
  • «فعّل الذكاء الاصطناعي» يثبّت Ollama ويشغّله تلقائياً   • «حالة الذكاء الاصطناعي»   • «الغ التثبيت»
Agent X 🕵️ (يتعلم بنفسه من GitHub):
  • «تعلم عن ...»   • «شغل ايجنت اكس» / «وقف ايجنت اكس»   • «ايجنت اكس علم نفسك»   • «تقرير ايجنت اكس»
المستندات 📊:
  • «اعمل عرض تقديمي عن ...» (أو «... 8 شرائح»، أو «... : نقطة، نقطة»)
  • «اكتب تقرير وورد عن ...»
التعلم الذاتي:
  • «إذا سألتك ... قل ...»   • «تذكر أن ... هو ...»   • «اسمي ...»
  • «الجواب الصحيح هو ...» لتصحيحي   • «صح» لتأكيد جوابي   • «انسى ...»
  • «وش تعلمت؟»
الإصلاح الذاتي:
  • «افحص نفسك»   • «اصلح نفسك»   • «الأعطال»   • «العقول»   • «المهارات»   • «نسخة احتياطية»"""

HELP_EN = """I can help with:
  • Conversation & questions (via Claude or Ollama when available, otherwise local knowledge)
  • Time & date: "what time is it"
  • Math: "calculate 15 * 4"
  • Notes: "note buy milk" / "my notes" / "done note 2"
  • System: "system status"
Voice 🎤:
  • mic button to talk, speaker button for spoken replies   • "voice on" / "mute"   • "say ..."   • "test voice"
Coding 👨‍💻:
  • "write a python script that ..."   • "run it" (auto-fixes errors)   • "modify the code: ..."   • "show the code"
Local AI 🧠:
  • "setup ai" installs and starts Ollama automatically   • "ai status"   • "cancel setup"
Agent X 🕵️ (self-teaching from GitHub):
  • "learn about ..."   • "start agent x" / "stop agent x"   • "agent x teach yourself"   • "agent x report"
Documents 📊:
  • "make a presentation about ..." (or "... 8 slides", or "...: point, point")
  • "write a word document about ..."
Self-learning:
  • "when I ask X say Y"   • "remember that X is Y"   • "my name is ..."
  • "the correct answer is ..." to correct me   • "correct" to confirm   • "forget ..."
  • "what have you learned"
Self-repair:
  • "diagnose"   • "heal yourself"   • "show errors"   • "brains"   • "skills"   • "backup\""""


def _report(checks, ar):
    lines = []
    for c in checks:
        mark = "⚠️" if c.warn else ("✅" if c.ok else "❌")
        lines.append(f"  {mark} {c.name}: {c.detail}")
    head = "نتيجة الفحص الذاتي:" if ar else "Self-diagnostic report:"
    return head + "\n" + "\n".join(lines)


def handle(text, match, jarvis):
    q = match.group(0)
    ar = jarvis.is_ar(text)
    if re.search(r"مساعد|ساعدني|تقدر|الاوامر|help|commands|what can", q):
        return HELP_AR if ar else HELP_EN

    if re.search(r"افحص|فحص|تشخيص|diagnose|check|diagnostics", q):
        return _report(jarvis.healer.health_check(), ar)

    if re.search(r"اصلح|صلح|عالج|heal|fix|repair", q):
        notes = jarvis.healer.heal_all()
        report = _report(jarvis.healer.health_check(), ar)
        if not notes:
            return ("ما فيه شيء يحتاج إصلاح.\n" if ar else "Nothing needed repair.\n") + report
        done = "\n".join(f"  🔧 {n}" for n in notes)
        return (("الإصلاحات اللي سويتها:\n" if ar else "Repairs performed:\n") + done + "\n" + report)

    if re.search(r"تعلمت|learn|know about me", q):
        facts = jarvis.memory.all_facts()
        qa = jarvis.memory.learned(15)
        if not facts and not qa:
            return jarvis.say("ما تعلمت شيء منك بعد. علمني!", "I haven't learned anything from you yet. Teach me!", text)
        out = []
        if facts:
            out.append("المعلومات:" if ar else "Facts:")
            out += [f"  • {f['key']}: {f['value']}" for f in facts[:15]]
        if qa:
            out.append("الأجوبة المتعلمة:" if ar else "Learned answers:")
            src = {"taught": "منك" if ar else "taught", "llm": "من الذكاء" if ar else "from LLM"}
            out += [f"  • {r['question']} → {r['answer'][:80]} ({src.get(r['source'], r['source'])})" for r in qa]
        return "\n".join(out)

    if re.search(r"عقل|عقول|brain", q):
        lines = [f"  • {name}: {status}" for name, status in jarvis.router.status()]
        return ("العقول (بالترتيب):\n" if ar else "Brains (in order):\n") + "\n".join(lines)

    if re.search(r"اعطال|اخطاء|errors", q):
        rows = jarvis.memory.recent_errors(8)
        if not rows:
            return jarvis.say("ما فيه أعطال مسجلة.", "No errors recorded.", text)
        lines = [f"  {'✅' if r['fixed'] else '•'} [{r['component']}] {r['error_type']}: {r['message'][:90]}"
                 + (f" → {r['fix_note']}" if r['fix_note'] else "") for r in rows]
        return ("آخر الأعطال:\n" if ar else "Recent errors:\n") + "\n".join(lines)

    if re.search(r"نسخه|backup", q):
        path = jarvis.memory.backup()
        return jarvis.say(f"تم حفظ نسخة احتياطية: {path.name}", f"Backup saved: {path.name}", text)

    if re.search(r"^(فعل|شغل|enable)", q):
        name = text.strip().split()[-1]
        ok = jarvis.skills.release(name)
        return jarvis.say(f"تم تفعيل مهارة {name}." if ok else f"مهارة {name} مو موقوفة.",
                          f"Skill {name} re-enabled." if ok else f"Skill {name} isn't quarantined.", text)

    lines = []
    for s in jarvis.skills.skills.values():
        state = "⛔ quarantined" if s.name in jarvis.skills.quarantined else ("❌ " + s.error if s.error else "✅")
        lines.append(f"  • {s.name}: {state}")
    return ("المهارات:\n" if ar else "Skills:\n") + "\n".join(lines)
