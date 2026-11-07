from datetime import datetime

NAME = "datetime"
PATTERNS = [
    r"(كم الساعه|الساعه كم|وش الوقت|كم الوقت|الوقت الحين)",
    r"(what time|current time|the time)",
    r"(التاريخ|اليوم كم|وش اليوم|اي يوم)",
    r"(what day|today'?s date|what is the date|the date)",
]
TESTS = ["كم الساعة", "what time is it", "what is the date"]

DAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
             "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def handle(text, match, jarvis):
    now = datetime.now()
    asks_date = any(w in match.group(0) for w in ("تاريخ", "يوم", "day", "date"))
    if asks_date:
        ar = f"اليوم {DAYS_AR[now.weekday()]} {now.day} {MONTHS_AR[now.month - 1]} {now.year}."
        en = now.strftime("Today is %A, %d %B %Y.")
    else:
        ar = f"الساعة الآن {now:%H:%M}."
        en = now.strftime("It is %H:%M.")
    return jarvis.say(ar, en, text)
