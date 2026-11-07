"""The offline brain: always available, no internet, no token.

It answers from what Jarvis has learned (taught answers, facts, answers cached
from earlier LLM replies) plus a small set of built-in conversational rules.
When it doesn't know, it says so and explains how to teach it.
"""
from __future__ import annotations

import random
import re

from ..text import is_arabic, normalize
from .base import Brain

RULES = [
    # (pattern on normalized text, arabic replies, english replies)
    (r"^(السلام عليكم|سلام عليكم)", ["وعليكم السلام {title}، كيف أقدر أخدمك اليوم؟", "وعليكم السلام ورحمة الله {title}، {name} في الخدمة."], []),
    (r"^(مرحبا|اهلا|هلا|هاي|صباح الخير|مساء الخير)\b", ["أهلاً {title}، كيف أقدر أخدمك اليوم؟", "أهلاً {title}، {name} في الخدمة."], []),
    (r"^(hi|hello|hey|good (morning|evening|afternoon))\b", [], ["Hello {title}. How may I assist you?", "At your service, {title}."]),
    (r"(كيف حالك|كيفك|شلونك|كيف الحال)", ["بأفضل حال {title}، كل الأنظمة تعمل. وأنت؟"], []),
    (r"how are you", [], ["All systems nominal, {title}. And you?"]),
    (r"(من انت|عرف بنفسك|وش اسمك|ما اسمك)", ["أنا {name}، مساعدك الشخصي. أتعلم منك وأصلح أعطالي بنفسي."], []),
    (r"(who are you|your name|introduce yourself)", [], ["I am {name}, your personal assistant. I learn from you and repair my own faults."]),
    (r"(شكرا|مشكور|يعطيك العافيه|تسلم)", ["العفو {title}، في الخدمة دائماً.", "لا شكر على واجب {title}."], []),
    (r"(thank you|thanks)", [], ["Always a pleasure, {title}.", "You're welcome, {title}."]),
    (r"(مع السلامه|تصبح على خير|باي)", ["في أمان الله {title}."], []),
    (r"(bye|good night|goodbye)", [], ["Goodbye, {title}."]),
]


class OfflineBrain(Brain):
    name = "offline"
    is_llm = False

    def __init__(self, memory, config):
        self.memory = memory
        self.config = config

    def available(self) -> bool:
        return True

    def status(self) -> str:
        return "ready (built-in, works without internet)"

    def ask(self, messages: list[dict], system: str = "") -> str:
        question = messages[-1]["content"] if messages else ""
        ar = is_arabic(question) or self.config["language"] == "ar"
        fmt = {"title": self.config["user_title"] if ar else "sir", "name": self.config["name"]}
        norm = normalize(question)

        for pattern, ar_replies, en_replies in RULES:
            if re.search(pattern, norm):
                replies = ar_replies if ar and ar_replies else (en_replies or ar_replies)
                return random.choice(replies).format(**fmt)

        hit = self.memory.recall(question, threshold=0.6)
        if hit:
            return hit[0]["answer"]

        facts = self.memory.search_facts(question)
        if facts:
            if ar:
                return "هذا ما أعرفه: " + "؛ ".join(f"{k}: {v}" for k, v in facts)
            return "Here is what I know: " + "; ".join(f"{k}: {v}" for k, v in facts)

        if ar:
            return ("للأسف ما أعرف الجواب بعد {title}، وأنا الآن أعمل بدون اتصال بذكاء خارجي. "
                    "علّمني بقول: «إذا سألتك {q} قل ...» وراح أحفظها.").format(q=question.strip(), **fmt)
        return (f"I don't know that yet, {fmt['title']}, and no external AI is reachable right now. "
                f"Teach me with: \"when I ask {question.strip()} say ...\"")
