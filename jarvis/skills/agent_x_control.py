"""Commands for Agent X (self-teaching from GitHub)."""
import re

NAME = "agent_x_control"
AGENT = r"(?:ايجنت اكس|ايجنت x|الايجنت|agent x|agentx)"
PATTERNS = [
    rf"^(?:يا\s+)?{AGENT}\s*[،,:]?\s*(?:تعلم|ادرس|اتعلم)\s+(?:عن|كيف)?\s*.+",
    r"^(?:تعلم|ادرس|اتعلم)\s+(?:عن|كيف)\s+.+",
    r"^(?:learn|study|research)\s+(?:about|how)\s+.+",
    rf"^(?:{AGENT}\s+learn|{AGENT}\s+study)\s+.+",
    rf"^(?:شغل|فعل|ابدا|ابدأ|start|enable|run)\s+{AGENT}$",
    rf"^{AGENT}\s+(?:ابدا|ابدأ|شغل|start|go)$",
    rf"^{AGENT}\s+(?:علم نفسك|تعلم بنفسك|teach yourself)$",
    rf"^(?:علم نفسك|teach yourself)$",
    rf"^(?:وقف|اوقف|طفي|stop|disable)\s+{AGENT}$",
    rf"^(?:وش|ايش|ماذا)\s+(?:تعلم|تعلمت)\s+{AGENT}$",
    rf"^(?:{AGENT}\s+(?:report|status|تقرير|حالة|حاله)|تقرير {AGENT}|agent x report|agent x status)$",
]
TESTS = ["agent x status"]


def _topic(text):
    t = re.sub(rf"^\s*(?:يا\s+)?{AGENT}\s*[،,:]?\s*", "", text.strip(), flags=re.I)
    t = re.sub(r"^\s*(?:learn|study|research|تعلم|تعلّم|ادرس|اتعلم)\s+(?:about|how to|how|عن|كيف)?\s*",
               "", t, flags=re.I)
    return t.strip(" ؟?.!")


def handle(text, match, jarvis):
    q = match.group(0)
    ax = jarvis.agent_x
    say = lambda ar, en: jarvis.say(ar, en, text)

    if re.match(r"^(?:وقف|اوقف|طفي|stop|disable)", q):
        ax.stop.set()
        jarvis.config.set("agent_x_auto", False)
        return say("أوقفت Agent X. تقدر تشغّله مرة ثانية بقول «شغل ايجنت اكس».",
                   "Agent X stopped. Say \"start agent x\" to resume.")

    if re.search(r"(تقرير|حاله|report|status|وش|ايش|ماذا)", q):
        st = ax.state
        lines = [say(f"• في الانتظار: {len(st['queue'])} موضوع", f"• queued: {len(st['queue'])} topic(s)"),
                 say(f"• تعلّم: {len(st['done'])} موضوع", f"• learned: {len(st['done'])} topic(s)"),
                 say("• يشتغل في الخلفية ✅" if ax.thread and ax.thread.is_alive() else "• متوقف",
                     "• running in the background ✅" if ax.thread and ax.thread.is_alive() else "• stopped")]
        recent = [e["msg"] for e in st["log"][-5:]]
        if recent:
            lines.append(say("آخر النشاط:", "Recent activity:"))
            lines += [f"  - {m[:160]}" for m in recent]
        return "🕵️ Agent X\n" + "\n".join(lines)

    if re.match(rf"^(?:شغل|فعل|ابدا|ابدأ|start|enable|run)\s+{AGENT}$|^{AGENT}\s+(?:ابدا|ابدأ|شغل|start|go)$", q):
        jarvis.config.set("agent_x_auto", True)
        started = ax.start()
        return say("🕵️ Agent X بدأ يشتغل في الخلفية: يدوّر على الأسئلة اللي ما عرفت أجاوبها ويتعلمها من GitHub، "
                   "وراح أبلغك بكل شيء يتعلمه." if started else "Agent X شغّال من قبل ✅",
                   "🕵️ Agent X is running in the background: it finds what I couldn't answer and learns it from "
                   "GitHub. I'll tell you what it learns." if started else "Agent X is already running ✅")

    if re.search(r"(علم نفسك|تعلم بنفسك|teach yourself)", q):
        gaps = ax.find_gaps()
        ax.learn_now(ax.state["queue"][0]) if ax.state["queue"] else None
        return say(f"🕵️ لقيت {len(gaps)} شيء جديد ما أعرفه، وبدأت أتعلم. في الانتظار: {len(ax.state['queue'])}.",
                   f"🕵️ Found {len(gaps)} new gap(s); learning now. Queue: {len(ax.state['queue'])}.")

    topic = _topic(text)
    if not topic:
        return say("وش تبيني أتعلم؟ مثال: «تعلم عن الطاقة الشمسية».", "What should I learn? e.g. \"learn about solar power\".")
    ax.learn_now(topic)
    return say(f"🕵️ Agent X بدأ يتعلم «{topic}» من GitHub… راح أبلغك أول ما يخلص.",
               f"🕵️ Agent X is studying \"{topic}\" on GitHub… I'll tell you when it's done.")
