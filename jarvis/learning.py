"""Self-learning.

Jarvis learns in four ways:
  1. Direct teaching  - "إذا سألتك X قل Y" / "when I ask X say Y" / "learn: X => Y"
  2. Facts            - "تذكر أن X هو Y" / "remember that X is Y" / "اسمي ..." / "call me ..."
  3. Feedback         - "صح"/"correct" raises an answer's score, "غلط"/"wrong" lowers it,
                        "الجواب الصحيح هو ..." / "the correct answer is ..." replaces it.
  4. From its own AI brains - answers that Claude/Ollama give to knowledge
                        questions are cached, so next time Jarvis answers them
                        offline, without any token.
"""
from __future__ import annotations

import re

from .text import normalize

F = re.IGNORECASE

TEACH = [
    re.compile(r"^(?:[اأإ]ذا|لو|لما|متى\s+ما)\s+(?:سألتك|سالتك|قلت\s+لك|قلتلك|قلت)\s+(?P<q>.+?)\s*[،,]?\s*"
               r"(?:ف?قل|ف?قول|ف?رد|ف?جاوب|ف?قولي)\s+(?P<a>.+)$", F),
    re.compile(r"^(?:when|if)\s+i\s+(?:ask|say|tell)(?:\s+you)?\s+(?P<q>.+?)\s*,?\s*"
               r"(?:then\s+)?(?:say|reply|answer|respond)(?:\s+with)?\s+(?P<a>.+)$", F),
    re.compile(r"^(?:learn|teach|تعلم|تعلّم)\s*[:：]\s*(?P<q>.+?)\s*(?:=>|->|=)\s*(?P<a>.+)$", F),
]
NAME = [
    re.compile(r"^(?:اسمي|انا\s+اسمي|أنا\s+اسمي|my\s+name\s+is|i\s+am\s+called)\s+(?P<v>.+)$", F),
    re.compile(r"^(?:ناديني|سمني|call\s+me)\s+(?P<v>.+)$", F),
]
FACT = [
    re.compile(r"^(?:تذكر|احفظ|اعرف|خلك\s+فاكر)\s+(?:[اأإ]ن\s+)?(?P<k>.+?)\s+(?:هو|هي|هم|يساوي|=)\s+(?P<v>.+)$", F),
    re.compile(r"^remember(?:\s+that)?\s+(?P<k>.+?)\s+(?:is|are|=)\s+(?P<v>.+)$", F),
    re.compile(r"^(?:تذكر|احفظ)\s+(?:[اأإ]ن\s+)?(?P<v>.+)$", F),
    re.compile(r"^remember(?:\s+that)\s+(?P<v>.+)$", F),
]
FORGET = [re.compile(r"^(?:انس|انسى|إنس|امسح\s+من\s+ذاكرتك|forget(?:\s+about)?)\s+(?P<k>.+)$", F)]
CORRECT = [
    re.compile(r"^(?:(?:خط[أا]|غلط)\s*[،,.!]*\s*)?(?:الجواب|الاجابه|الإجابة|الاجابة)\s+"
               r"(?:الصحيح|الصحيحه|الصحيحة|الصح)\s*(?:هو|هي)?\s*[:：]?\s*(?P<a>.+)$", F),
    re.compile(r"^(?:خط[أا]|غلط)\s*[،,.!]+\s*(?:الصح|الصحيح)\s*(?:هو|هي)?\s*[:：]?\s*(?P<a>.+)$", F),
    re.compile(r"^(?:wrong|incorrect|no)[,.!]*\s+(?:the\s+(?:correct\s+|right\s+)?answer\s+is|it'?s|it\s+is)\s+(?P<a>.+)$", F),
    re.compile(r"^the\s+(?:correct|right)\s+answer\s+is\s+(?P<a>.+)$", F),
]
FACT_QUESTION = re.compile(
    r"^(?:ما\s+هو|ما\s+هي|ماهو|ماهي|وش|ايش|من\s+هو|من\s+هي|what\s+is|what'?s|who\s+is|tell\s+me)\s+(?P<k>.+?)\s*[؟?]?$", F)
POSITIVE = {"صح", "صحيح", "ممتاز", "احسنت", "برافو", "بالضبط", "تمام", "correct", "right", "exactly",
            "perfect", "good job", "well done", "good answer"}
NEGATIVE = {"خطا", "غلط", "مو صحيح", "مب صحيح", "wrong", "incorrect", "thats wrong", "that's wrong", "not right"}

# Questions whose answers change over time are never cached.
VOLATILE = re.compile(r"(اليوم|الحين|الان|حاليا|امس|بكره|غدا|اخبار|طقس|سعر|اسعار|now|today|tomorrow|yesterday|"
                      r"latest|current|news|weather|price|score)", F)
QUESTION_HINT = re.compile(r"([?؟]|^(ما|ماذا|من|متى|اين|وين|كيف|ليش|لماذا|كم|هل|وش|ايش|اشرح|عرف|"
                           r"what|who|when|where|why|how|which|explain|define)\b)", F)


def _clean(s: str) -> str:
    return s.strip().strip("\"'«»“”").strip()


class Learner:
    def __init__(self, jarvis):
        self.j = jarvis
        self.last_question: str | None = None
        self.last_qa_id: int | None = None

    def remember_exchange(self, question: str, qa_id: int | None) -> None:
        self.last_question, self.last_qa_id = question, qa_id

    def _restore_last_question(self) -> None:
        """After a restart, recover the last answered question from the conversation log."""
        if self.last_question:
            return
        rows = self.j.memory.recent(6)
        for i in range(len(rows) - 1, 0, -1):
            if rows[i]["role"] == "assistant" and rows[i]["source"].startswith(("brain:", "memory")) \
                    and rows[i - 1]["role"] == "user":
                self.last_question = rows[i - 1]["text"]
                hit = self.j.memory.recall(self.last_question, threshold=0.95)
                self.last_qa_id = hit[0]["id"] if hit else None
                return

    # ------------------------------------------------------------------
    def process(self, text: str) -> str | None:
        """Handle teaching/feedback phrases. Returns a reply, or None if not a lesson."""
        t = text.strip().rstrip(".!")
        say = lambda ar, en: self.j.say(ar, en, text)
        mem = self.j.memory
        self._restore_last_question()

        for p in TEACH:
            m = p.match(t)
            if m:
                q, a = _clean(m["q"]), _clean(m["a"])
                mem.learn_answer(q, a, "taught")
                return say(f"تم {self.j.title(text)}، إذا سألتني «{q}» راح أقول: {a}",
                           f"Understood. When you ask \"{q}\" I'll answer: {a}")

        for i, p in enumerate(NAME):
            m = p.match(t)
            if m:
                v = _clean(m["v"])
                mem.set_fact("اسم المستخدم", v)
                self.j.config.set("user_title", v)
                return say(f"تشرفنا يا {v}، حفظت اسمك.", f"A pleasure, {v}. I'll remember that.")

        m = None
        for p in FORGET:
            m = p.match(t)
            if m:
                n = mem.forget_fact(_clean(m["k"]))
                return say(f"تم، نسيت {n} معلومة." if n else "ما كنت أعرف شيء عن هذا أصلاً.",
                           f"Done, forgot {n} item(s)." if n else "I didn't know anything about that.")

        for p in CORRECT:
            m = p.match(t)
            if m:
                a = _clean(m["a"])
                if not self.last_question:
                    return say("ما فيه سؤال سابق أصححه.", "There's no previous question to correct.")
                if self.last_qa_id:
                    mem.correct_answer(self.last_qa_id, a)
                else:
                    self.last_qa_id = mem.learn_answer(self.last_question, a, "taught")
                return say(f"شكراً على التصحيح، حفظت أن جواب «{self.last_question}» هو: {a}",
                           f"Thanks for the correction. The answer to \"{self.last_question}\" is now: {a}")

        for p in FACT:
            m = p.match(t)
            if m:
                v = _clean(m["v"])
                k = _clean(m.groupdict().get("k") or v)
                mem.set_fact(k, v)
                return say(f"حفظتها: {k} ← {v}" if k != v else f"حفظتها: {v}",
                           f"Noted: {k} → {v}" if k != v else f"Noted: {v}")

        norm = normalize(t)
        if norm in {normalize(x) for x in POSITIVE} and self.last_qa_id:
            mem.rate_answer(self.last_qa_id, +0.5)
            return say("ممتاز، راح أعتمد هذا الجواب أكثر.", "Good, I'll trust that answer more.")
        if norm in {normalize(x) for x in NEGATIVE} and self.last_question:
            if self.last_qa_id:
                mem.rate_answer(self.last_qa_id, -1.0)
            return say("آسف! وش الجواب الصحيح؟ قل: «الجواب الصحيح هو ...»",
                       "Sorry! What is the right answer? Say: \"the correct answer is ...\"")
        return None

    # ------------------------------------------------------------------
    def fact_answer(self, text: str) -> str | None:
        m = FACT_QUESTION.match(text.strip())
        if not m:
            return None
        value = self.j.memory.get_fact(m["k"])
        if value is None and normalize(m["k"]) in {"اسمي", "my name"}:
            value = self.j.memory.get_fact("اسم المستخدم")
        return value

    def learn_from_llm(self, question: str, answer: str) -> int | None:
        """Cache an AI brain's answer so it is available offline next time."""
        if not self.j.config["learn_from_llm"]:
            return None
        q = question.strip()
        if len(q) > 300 or len(answer) > 3000 or VOLATILE.search(normalize(q)) or not QUESTION_HINT.search(q):
            return None
        return self.j.memory.learn_answer(q, answer, "llm")
