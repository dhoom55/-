"""Programming commands.

  اكتب برنامج بايثون يحسب المعدل          write a python script that renames files
  شغل الكود / run it                        اصلح الكود / fix the code
  عدل الكود: خله يحفظ النتيجة في ملف        modify the code: add a menu
  وين الكود / show the code
"""
import re

from jarvis.brains import BrainError
from jarvis.coder import Coder
from jarvis.office import open_file

NAME = "coding"
VERB = r"(?:اكتب|اكتبلي|برمج|برمجلي|سو|سوي|سويلي|اعمل|اعمللي|انشي|صمم|ابني|ابغى|ابي|اريد|write|create|make|build|code|program|develop)"
WHAT = (r"(?:كود|برنامج|سكربت|سكريبت|داله|كلاس|تطبيق|موقع|صفحه ويب|لعبه|بوت|اداه|"
        r"code|program|script|function|class|app|application|website|web page|webpage|game|bot|tool|api|cli)")
PATTERNS = [
    rf"^{VERB}\s+(?:لي\s+|me\s+)?(?:an?\s+|the\s+)?(?:\S+\s+)?{WHAT}\b",
    r"^(?:برمج|برمجلي)\s+\S+",
    r"^(?:شغل|نفذ|جرب)\s+(?:الكود|البرنامج|السكربت|المشروع)$",
    r"^(?:run|execute|test)\s+(?:it|the code|the program|the script|my code|my program)$",
    r"^(?:اصلح|صلح)\s+(?:الكود|البرنامج|السكربت)",
    r"^fix\s+(?:the\s+|my\s+)?(?:code|program|script|bug)",
    r"^(?:عدل|غير|طور|حسن|ضيف|اضف)\s+(?:على\s+|في\s+)?(?:الكود|البرنامج|السكربت)",
    r"^(?:modify|change|update|improve|edit)\s+(?:the\s+|my\s+)?(?:code|program|script)",
    r"^(?:وين الكود|اعرض الكود|افتح الكود|افتح مجلد الكود|show the code|show code|open the code|where is the code)$",
]
TESTS = []   # covered by unit tests with a fake AI brain


def _preview(paths, limit=40):
    out = []
    for p in paths:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        body = "\n".join(lines[:limit]) + ("\n…" if len(lines) > limit else "")
        out.append(f"📄 {p.name}\n```\n{body}\n```")
    return "\n".join(out)


def _run_report(jarvis, coder, text):
    r = coder.run()
    say = lambda ar, en: jarvis.say(ar, en, text)
    fixed = ""
    if r.fixes:
        fixed = say(f"🔧 صلّحت الكود {len(r.fixes)} مرة تلقائياً حتى اشتغل.\n",
                    f"🔧 Auto-fixed the code {len(r.fixes)} time(s).\n")
    if r.note == "gui":
        return say("🚀 فتحت البرنامج (له نافذة خاصة).", "🚀 Started the program (it opens its own window).")
    if r.note == "opened":
        return say(f"🌐 فتحت الصفحة في المتصفح: {r.output}", f"🌐 Opened the page in your browser: {r.output}")
    if r.note == "nothing":
        return say(f"ما لقيت شيء أشغله: {r.output}", f"Nothing to run: {r.output}")
    if r.note == "timeout":
        return say(f"⏱️ البرنامج طوّل أكثر من {jarvis.config['code_timeout']} ثانية فأوقفته.\n{r.output[-800:]}",
                   f"⏱️ The program ran longer than {jarvis.config['code_timeout']}s, so I stopped it.\n{r.output[-800:]}")
    if r.note == "needs_input":
        return say(f"البرنامج ينتظر منك تكتب له مدخلات، شغّله بنفسك من المجلد:\n📁 {coder.current()}",
                   f"The program waits for keyboard input - run it yourself from:\n📁 {coder.current()}")
    if r.ok:
        return fixed + say(f"✅ اشتغل البرنامج بنجاح. المخرجات:\n```\n{r.output[-1500:] or '(لا شيء)'}\n```",
                           f"✅ The program ran successfully. Output:\n```\n{r.output[-1500:] or '(nothing)'}\n```")
    tail = r.output[-1200:]
    if not r.fixes and not _has_ai(jarvis):
        return say(f"❌ البرنامج فيه خطأ:\n```\n{tail}\n```\nأقدر أصلحه تلقائياً إذا كان Claude أو Ollama متصل.",
                   f"❌ The program failed:\n```\n{tail}\n```\nI can fix it automatically when Claude or Ollama is connected.")
    return fixed + say(f"❌ حاولت أصلحه {len(r.fixes)} مرات وما زال فيه خطأ:\n```\n{tail}\n```",
                       f"❌ Tried {len(r.fixes)} fix(es) but it still fails:\n```\n{tail}\n```")


def _has_ai(jarvis):
    return any(b.is_llm and b.available() for b in jarvis.router.brains)


NO_AI_AR = ("البرمجة تحتاج عقل ذكاء اصطناعي، وما فيه واحد متصل الحين.\n"
            "• مجاناً وبدون إنترنت: ثبّت Ollama من ollama.com ثم اكتب في الطرفية: ollama pull qwen2.5-coder\n"
            "• أو أضف مفتاح Claude (ANTHROPIC_API_KEY).\nبعدها اطلب مني مرة ثانية.")
NO_AI_EN = ("Programming needs an AI brain and none is connected right now.\n"
            "• Free and offline: install Ollama from ollama.com, then run: ollama pull qwen2.5-coder\n"
            "• Or add a Claude key (ANTHROPIC_API_KEY).\nThen ask me again.")


def handle(text, match, jarvis):
    q = match.group(0)
    coder = Coder(jarvis)
    say = lambda ar, en: jarvis.say(ar, en, text)

    if re.match(r"^(?:وين|اعرض|افتح|show|open|where)", q):
        folder = coder.current()
        if not folder:
            return say("ما كتبت أي كود للحين.", "I haven't written any code yet.")
        open_file(folder)
        return say(f"📁 {folder}\n", f"📁 {folder}\n") + _preview(coder.source_files(folder))

    if re.match(r"^(?:شغل|نفذ|جرب|run|execute|test|اصلح|صلح|fix)", q):
        return _run_report(jarvis, coder, text)

    try:
        if re.match(r"^(?:عدل|غير|طور|حسن|ضيف|اضف|modify|change|update|improve|edit)", q):
            project = coder.modify(text)
            head = say(f"✏️ عدّلت الكود ({project.brain}).", f"✏️ Updated the code ({project.brain}).")
        else:
            project = coder.write(text)
            head = say(f"👨‍💻 كتبت البرنامج ({project.brain}).", f"👨‍💻 Wrote the program ({project.brain}).")
    except BrainError:
        return say(NO_AI_AR, NO_AI_EN)
    except FileNotFoundError:
        return say("ما فيه مشروع كود أعدّل عليه، اطلب مني أكتب برنامج أول.",
                   "There's no code project to modify yet - ask me to write one first.")

    hint = say("قل «شغل الكود» عشان أجربه وأصلح أي خطأ تلقائياً.",
               "Say \"run it\" and I'll test it and fix any error automatically.")
    return "\n".join(x for x in (head, project.explanation[:800], _preview(project.files), f"📁 {project.folder}", hint) if x)
