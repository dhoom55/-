"""Voice commands: turn spoken replies on/off, say something, check the voice engines."""
import re

NAME = "voice_control"
PATTERNS = [
    r"^(فعل الصوت|شغل الصوت|تكلم معي|كلمني بصوت|رد بالصوت|voice on|enable voice|speak replies|talk to me)$",
    r"^(اسكت|وقف الصوت|طفي الصوت|اقفل الصوت|بدون صوت|voice off|disable voice|mute|stop talking|be quiet)$",
    r"^(قل|قول|انطق|say|speak)\s+.+",
    r"^(اختبر الصوت|حاله الصوت|فحص الصوت|test voice|voice status|check voice)$",
]
TESTS = ["حالة الصوت", "voice status"]


def handle(text, match, jarvis):
    q = match.group(0)
    voice = jarvis.voice
    if re.match(r"^(فعل|شغل|تكلم|كلمني|رد بالصوت|voice on|enable|speak replies|talk)", q):
        jarvis.config.set("speak_replies", True)
        return jarvis.say("تم، راح أرد عليك بالصوت من الحين.", "Voice replies are on.", text)
    if re.match(r"^(اسكت|وقف|طفي|اقفل|بدون|voice off|disable|mute|stop|be quiet)", q):
        jarvis.config.set("speak_replies", False)
        voice.speaker.stop()
        return jarvis.say("تم، أوقفت الصوت.", "Voice replies are off.", text)
    if re.match(r"^(اختبر|حاله|فحص|test|voice status|check)", q):
        out = voice.status()
        spoken = jarvis.say("هذا اختبار للصوت.", "This is a voice test.", text)
        try:
            engine = voice.speaker.speak(spoken)
            out += "\n" + jarvis.say(f"✅ نطقت جملة تجريبية بمحرك {engine}.", f"✅ Spoke a test sentence with {engine}.", text)
        except Exception as exc:
            out += "\n" + jarvis.say(f"❌ ما قدرت أنطق: {exc}", f"❌ Could not speak: {exc}", text)
        return out
    # "say ..." - speak the rest of the sentence
    words = re.sub(r"^\s*(قل|قول|انطق|say|speak)\s+", "", text.strip(), flags=re.IGNORECASE)
    voice.speaker.speak_async(words, on_error=lambda e: jarvis.healer.record("voice", e, quiet=True))
    return words
