"""Install / start / check the free local AI brain (Ollama)."""
import re

NAME = "ai_control"
PATTERNS = [
    r"^(?:فعل|ثبت|نزل|شغل|حمل)\s+(?:الذكاء الاصطناعي|الذكاء|العقل|اولاما|olama|ollama)",
    r"^(?:install|setup|set up|enable|start|activate)\s+(?:the\s+)?(?:local\s+)?(?:ai|ollama|brain)\b",
    r"^(?:حاله|وضع)\s+(?:الذكاء الاصطناعي|التثبيت|اولاما|ollama)$",
    r"^(?:ai status|ollama status|setup status)$",
    r"^(?:الغ|وقف|اوقف)\s+(?:التثبيت|التحميل)$",
    r"^(?:cancel|stop)\s+(?:the\s+)?(?:setup|install|download)$",
]
TESTS = ["ai status"]


def handle(text, match, jarvis):
    q = match.group(0)
    setup = jarvis.ai_setup
    say = lambda ar, en: jarvis.say(ar, en, text)

    if re.match(r"^(?:الغ|وقف|اوقف|cancel|stop)", q):
        if setup.thread and setup.thread.is_alive():
            setup.cancel.set()
            return say("جاري إيقاف التثبيت…", "Stopping the setup…")
        return say("ما فيه تثبيت شغّال.", "No setup is running.")

    if re.match(r"^(?:حاله|وضع|ai status|ollama status|setup status)", q):
        st = setup.status()
        lines = [
            say("Ollama مثبت" if st["installed"] else "Ollama غير مثبت",
                "Ollama installed" if st["installed"] else "Ollama not installed"),
            say("الخادم شغّال" if st["running"] else "الخادم متوقف",
                "server running" if st["running"] else "server stopped"),
            say("النماذج: ", "models: ") + (", ".join(st["models"]) or "-"),
        ]
        if st["stage"] not in ("idle", "done"):
            lines.append(say("المرحلة: ", "stage: ") + f"{st['stage']} {st['progress']}")
        if st["error"]:
            lines.append("❌ " + st["error"])
        return "\n".join(f"• {x}" for x in lines)

    # install / activate
    if jarvis.has_ai() and setup.server_up():
        return say("الذكاء الاصطناعي المحلي شغّال وجاهز ✅", "The local AI is already running ✅")
    if not setup.start():
        return say(f"التثبيت شغّال من قبل… {setup.progress}", f"Setup is already running… {setup.progress}")
    if setup.exe():
        return say("Ollama مثبت، أشغّله وأتأكد إن النموذج موجود… راح أبلغك أول ما يجهز.",
                   "Ollama is installed - starting it and checking the model… I'll tell you when it's ready.")
    return say("بدأت أنزّل Ollama وأثبته، وبعدها أنزّل نموذج ذكاء يناسب جهازك (1 إلى 5 جيجا). "
               "تقدر تكمل استخدامي عادي، وراح أبلغك بالتقدم. لإيقافه قل «الغ التثبيت».",
               "Downloading and installing Ollama, then a model that fits your computer (1-5 GB). "
               "Keep using me meanwhile - I'll report progress. Say \"cancel setup\" to stop.")
