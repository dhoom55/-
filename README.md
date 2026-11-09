# جارفيس — مساعدك الشخصي الذكي 🤖

مساعد شخصي مكتوب بـ Python، **يتعلم بنفسه** و**يصلح أعطاله بنفسه**، ويشتغل **مع أو بدون** توكن Claude.

## 🖥️ تطبيق سطح المكتب

![واجهة جارفيس](docs/screenshot.png)

**الطريقة الأسهل:** فك ضغط `Jarvis-Desktop.zip` على سطح المكتب، ثم افتح مجلد `Jarvis` واضغط مرتين على:
- **ويندوز:** `Start Jarvis.bat` أو `Jarvis.pyw`
- **ماك:** `Start Jarvis.command`
- **لينكس:** `start-jarvis.sh`

هذا يحتاج Python 3.10 أو أحدث من [python.org](https://www.python.org/downloads/)، ولا يحتاج أي مكتبة إضافية.

**من المستودع:** أمر واحد ينسخ كل شيء إلى `سطح المكتب/Jarvis` ويضع اختصاراً على سطح المكتب:
```bash
python install_desktop.py
```

كل ملفات جارفيس تكون داخل مجلد واحد على سطح المكتب: البرنامج في `jarvis/`، والذاكرة والإعدادات والنسخ الاحتياطية والسجلات ومهاراتك في `data/`. تقدر تنقل المجلد لأي مكان ويكمل شغّال.

**بدون تثبيت Python:** يُبنى `Jarvis.exe` تلقائياً عبر GitHub Actions، أو يدوياً بـ `pip install pyinstaller` ثم `python build_exe.py`.

## سطر الأوامر

```bash
python -m jarvis              # محادثة
python -m jarvis -c "كم الساعة"
python -m jarvis --doctor     # فحص ذاتي
python -m jarvis --heal       # إصلاح ذاتي
python -m jarvis --rollback   # التراجع عن إصلاحات الكود
python -m unittest discover -s tests   # الاختبارات
```

لا يحتاج أي مكتبة خارجية للتشغيل، فقط Python 3.10 أو أحدث.

## 🧠 الذكاء الاصطناعي المحلي (تثبيت وتفعيل تلقائي)

أول ما تفتح تطبيق سطح المكتب، إذا ما كان فيه ذكاء اصطناعي متصل، جارفيس يسوي الخطوات هذي بنفسه:
1. يحمّل [Ollama](https://ollama.com) ويثبّته بصمت. في ويندوز يستخدم المثبّت الرسمي، وفي الماك يحطه في `~/Applications`، وفي لينكس يحطه في `~/.local` بدون صلاحيات مدير.
2. يشغّله.
3. يحمّل نموذج **qwen2.5** يناسب ذاكرة جهازك، وهو يعرف العربي والبرمجة:
   - 16 جيجا رام أو أكثر: `7b` (~4.7 جيجا)
   - 8 جيجا: `3b` (~1.9 جيجا)
   - أقل من كذا: `1.5b`
4. يحوّل نفسه عليه.

**التقدّم:** تشوفه في المحادثة وتقدر تكمل استخدام جارفيس خلال التحميل.

**الأوامر:** «فعّل الذكاء الاصطناعي» / «حالة الذكاء الاصطناعي» / «الغ التثبيت».

**إصلاح ذاتي:** إذا كان Ollama مثبت لكنه متوقف، جارفيس يشغّله تلقائياً عند الفحص الذاتي.

**مجرّب فعلياً:** في GitHub Actions، جارفيس يثبّت Ollama الحقيقي على Windows وmacOS وLinux، ويحمّل نموذجاً، ويجاوب منه.

## 🕵️ Agent X: يتعلم بنفسه من GitHub

Agent X يشتغل في الخلفية، ويسوي الخطوات هذي:
1. يدوّر على الأسئلة اللي ما عرف جارفيس يجاوبها، أو المواضيع اللي تطلبها بقول «تعلم عن ...».
2. يبحث عنها في GitHub ويحمّل وثائق أفضل المستودعات.
3. يتعلم منها بالذكاء الاصطناعي، أو يحفظ ملخصاً مع المصادر إذا ما فيه ذكاء اصطناعي.
4. يحفظ كل شيء في الذاكرة، فيصير جارفيس يجاوب عليه بعدين بدون إنترنت.

وإذا كان الطلب «فعل» (مثل «حوّل 100 درجة مئوية»)، الذكاء الاصطناعي يكتب مهارة جديدة.

**🛡️ الأمان:**
- Agent X **يقرأ اللي يحمّله ولا يشغّله أبداً**.
- المهارات اللي يكتبها تمر بفحص أمان: ممنوع حذف الملفات، وتشغيل الأوامر، وeval، وsubprocess.
- ولازم تنجح اختباراتها في عملية معزولة قبل ما تتثبت.
- ما يكتب فوق شيء علّمته أنت لجارفيس.
- حده 10 مواضيع في اليوم.

**الأوامر:** «تعلم عن ...» / «شغل ايجنت اكس» / «وقف ايجنت اكس» / «ايجنت اكس علم نفسك» / «تقرير ايجنت اكس».

**الحدود والتشغيل:** إذا عرّفت متغير البيئة `GITHUB_TOKEN`، يصير حد GitHub أعلى. ويشتغل تلقائياً مع تطبيق سطح المكتب.

**الخطة الكاملة:** [PLAN.md](PLAN.md).

## 🎤 الصوت

- **في النافذة:** زر 🎤 تتكلم بدل ما تكتب، وزر 🔊 يخلي جارفيس يرد بالصوت.
- **بالأوامر:** «فعّل الصوت» / «اسكت» / «قل ...» / «اختبر الصوت».
- **من سطر الأوامر:** `python -m jarvis --voice` محادثة كاملة بالصوت، و`--say "نص"` ينطق جملة.

| | يجرّب أولاً | وإذا ما نفع |
|---|---|---|
| **النطق** | أصوات طبيعية بالعربي والإنجليزي (edge-tts، يحتاج إنترنت) | صوت الجهاز نفسه بدون إنترنت: Windows SAPI أو `say` في الماك أو espeak في لينكس |
| **الاستماع** | Google (يدعم العربي، يحتاج إنترنت) | التعرّف المحلي في ويندوز (إنجليزي) |

إذا فشل محرك صوت، جارفيس ينتقل للي بعده ويوقف المحرك المتعطل 5 دقائق.

## 👨‍💻 البرمجة

| قل | يصير |
|---|---|
| `اكتب برنامج بايثون يحسب معدل الطلاب` | يكتب البرنامج ويحفظه في مجلد خاص |
| `شغل الكود` | يشغّله. إذا طلع خطأ يرسله للذكاء الاصطناعي ويصلحه ويعيد التشغيل، حتى 3 مرات |
| `عدل الكود: خله يحفظ النتيجة في ملف` | يعدّل المشروع الحالي |
| `وين الكود` | يفتح المجلد ويعرض الملفات |

- **حدود التشغيل:** كل برنامج له حد زمني 30 ثانية. البرامج اللي لها نافذة تنفتح بشكل مستقل.
- **النسخ القديمة:** تنحفظ في مجلد `.history`.
- **ملاحظة:** كتابة الكود وإصلاحه تحتاج عقل ذكاء اصطناعي. الأسهل والمجاني [Ollama](https://ollama.com)، بعد تثبيته اكتب `ollama pull qwen2.5-coder`. أما التشغيل نفسه فيشتغل بدون إنترنت.

## 📊 العروض التقديمية والوورد

| قل | يصير |
|---|---|
| `اعمل عرض تقديمي عن الطاقة الشمسية` | عرض PowerPoint بتصميم جاهز: شريحة عنوان، وشرائح محتوى، وشريحة ختام |
| `سوي بوربوينت عن مشروعي 8 شرائح` | يحدد عدد الشرائح |
| `اعمل عرض عن مشروعي: الفكرة، السوق، الميزانية` | شريحة لكل نقطة تعطيه إياها |
| `اكتب تقرير وورد عن السلامة في المصانع` | مستند Word بعنوان وأقسام وفقرات |

- **العربي:** يُكتب من اليمين لليسار بشكل صحيح في PowerPoint وWord.
- **مكان الملفات:** في مجلد `ملفات جارفيس` داخل مجلد جارفيس على سطح المكتب، ويفتح الملف تلقائياً.
- **من يكتب المحتوى:** إذا كان Claude أو Ollama متصل، هو يكتبه. إذا ما كان متصل، يجهّز لك هيكل جاهز تعبّيه، أو يبنيه من النقاط اللي تعطيه.

## العقول: لا يعتمد على توكن Claude

يجرّب جارفيس العقول بالترتيب، وإذا فشل واحد ينتقل للي بعده تلقائياً:

| العقل | متى يشتغل |
|---|---|
| **Claude** | إذا ثبّتت `pip install anthropic` ووضعت `ANTHROPIC_API_KEY` |
| **Ollama** (نموذج محلي ومجاني) | إذا كان [Ollama](https://ollama.com) شغّال على جهازك (`ollama pull llama3.2`) |
| **Offline** (العقل المحلي) | **دائماً**، بدون إنترنت وبدون توكن، ويجاوب من الأشياء اللي تعلّمها |

إذا تعطّل عقل (توكن خاطئ، أو انقطاع، أو حد الاستخدام)، يتوقف جارفيس عن استخدامه فترة تبدأ من 30 ثانية وتتضاعف مع كل فشل، ويكمل بالعقل اللي بعده.

## التعلم الذاتي

| قل | يصير |
|---|---|
| `إذا سألتك من صنعك قل صنعني عبدالله` | يحفظ السؤال وجوابه |
| `تذكر أن لون سيارتي هو أسود` ثم `ما هو لون سيارتي` | يحفظ المعلومة ويسترجعها |
| `اسمي عبدالله` / `ناديني أبو فهد` | يناديك بالاسم |
| `الجواب الصحيح هو ...` | يصحح آخر جواب قاله |
| `صح` / `غلط` | يرفع ثقته في الجواب أو ينزّلها |
| `انسى ...` | يحذف المعلومة |
| `وش تعلمت؟` | يعرض كل اللي تعلّمه |

**يتعلم من الذكاء الاصطناعي أيضاً:** الأسئلة المعرفية اللي يجاوب عليها Claude أو Ollama تنحفظ، فإذا انقطع التوكن لاحقاً يقدر يجاوب عليها من ذاكرته. الأسئلة اللي تتغير إجاباتها، مثل الطقس والأخبار والأسعار، ما تنحفظ.

## الإصلاح الذاتي

| العطل | الإصلاح |
|---|---|
| قاعدة الذاكرة تلفت | يسترجع آخر نسخة احتياطية سليمة، أو يبدأ ذاكرة جديدة |
| ملف `config.json` خربان | يحتفظ بنسخة من الملف التالف ويرجع للإعدادات الافتراضية |
| مكتبة ناقصة | يثبّتها بـ pip، **فقط من قائمة مسموحة** |
| مهارة تتعطل بشكل متكرر | يطلب من Claude أو Ollama إصلاح الكود، **ويختبر الإصلاح قبل ما يطبقه**، ويحفظ نسخة من الأصل |
| مهارة ما انصلحت | يوقفها (حجر) ويكمل الباقي شغّال. لإرجاعها: `فعّل مهارة X` |
| عقل متعطل | يتجاوزه مؤقتاً ويرجع له بعد فترة التهدئة |

**يتعلم أي إصلاح ينفع:** كل محاولة إصلاح تنسجّل مع نتيجتها، والمرة الجاية يبدأ بالإصلاح اللي نجح أكثر مع نفس نوع العطل.

أوامر الإصلاح داخل المحادثة: `افحص نفسك`، `اصلح نفسك`، `الأعطال`، `العقول`، `المهارات`، `نسخة احتياطية`.

## أضف مهاراتك الخاصة

أنشئ ملفاً في `~/.jarvis/plugins/weather.py`:

```python
NAME = "weather"
PATTERNS = [r"(طقس|weather)"]
TESTS = ["كيف الطقس"]          # مدخلات لازم ما تسبب عطل، ويستخدمها الإصلاح الذاتي للتحقق

def handle(text, match, jarvis):
    return jarvis.say("الطقس جميل اليوم", "The weather is nice", text)
```

## مكان الملفات

| المحتوى | المكان |
|---|---|
| الكود | `jarvis/`: الدماغ (`brains/`) والمهارات (`skills/`) والذاكرة والتعلم والإصلاح |
| بياناتك | `~/.jarvis/`، ويمكن تغييره بـ `JARVIS_HOME` |

ملفات البيانات داخل `~/.jarvis/`:
- `memory.db`: الذاكرة
- `config.json`: الإعدادات
- `plugins/`: مهاراتك
- `backups/`: النسخ الاحتياطية
- `logs/errors.log`: سجل الأعطال

والملفات اللي يسويها لك (العروض، والمستندات، والأكواد) تنحفظ في `ملفات جارفيس/` بجانب `data/` في تطبيق سطح المكتب، أو في `~/.jarvis/outputs/` من سطر الأوامر.

## مهارات Claude Code المحمّلة من GitHub

في `.claude/skills/` مهارات تساعد Claude Code لما يطوّر جارفيس معك:

| المهارة | المصدر | الفائدة |
|---|---|---|
| `skill-creator` | anthropics/skills | إنشاء مهارات جديدة وتحسينها |
| `mcp-builder` | anthropics/skills | ربط جارفيس بخدمات خارجية (MCP) |
| `webapp-testing` | anthropics/skills | اختبار واجهة ويب لجارفيس مستقبلاً |
| `frontend-design` | anthropics/skills | تصميم واجهة بأسلوب HUD |
| `systematic-debugging` | obra/superpowers | تتبّع جذور الأعطال |
| `test-driven-development` | obra/superpowers | كتابة الاختبار قبل الكود |
| `writing-plans` | obra/superpowers | تخطيط المهام الكبيرة |
| `verification-before-completion` | obra/superpowers | التحقق قبل إعلان انتهاء المهمة |

التراخيص: مهارات anthropics/skills بترخيص Apache-2.0، ومهارات obra/superpowers بترخيص MIT. كل مهارة معها ملف ترخيصها، والتفاصيل في `.claude/skills/SOURCES.md`.

---

## English summary

Jarvis is a personal assistant in pure Python (stdlib only).

- **Brains:** It tries Claude first (when the `anthropic` SDK and a key are present), then a local Ollama model, then a built-in offline brain that always works. Any brain that fails is skipped for a back-off period.
- **Self-learning:** It learns from direct teaching, stored facts and your corrections. It also caches knowledge answers from the LLM brains so they keep working offline.
- **Local AI auto-setup:** on first launch with no AI brain, Jarvis downloads, installs and starts Ollama on its own, pulls a qwen2.5 model sized to the machine's RAM, and switches to it. The healer restarts Ollama if it's stopped. CI verifies this end to end on real Windows, macOS and Linux.
- **Agent X (self-teaching):** a background agent that turns unanswered questions and requested topics into GitHub research. It downloads READMEs (never runs downloaded code), digests them with the AI or keeps an extractive summary with sources, and stores Q&A in memory for offline use. For action requests it can write a new skill, which must pass an AST safety check and its own tests in an isolated process. Daily limit, optional `GITHUB_TOKEN`.
- **Voice:**
  - Speaking uses natural edge-tts voices when online, otherwise the system's offline voice (SAPI, `say`, or espeak).
  - Listening uses Google speech recognition (Arabic) when online, otherwise Windows' offline dictation.
  - The desktop window has 🎤 and 🔊 buttons, and `python -m jarvis --voice` runs a hands-free conversation.
- **Coding:** Jarvis writes programs, runs them with a time limit (also from inside `Jarvis.exe`), and auto-fixes errors with the AI brain, keeping the old versions.
- **Documents:** Jarvis makes PowerPoint and Word files, with proper Arabic right-to-left layout and XML elements in schema order.
- **Self-repair:**
  - Restores corrupted memory from backups.
  - Resets a broken config.
  - Installs allow-listed missing packages.
  - Has an LLM rewrite a crashing skill, but only applies the rewrite after it passes tests, with a backup kept and rollback available. Otherwise it quarantines the skill.
  - Learns which repair strategies work.

Run `python -m jarvis` to start and `python -m unittest discover -s tests` to test.
