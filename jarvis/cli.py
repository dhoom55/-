"""Command line interface.

    python -m jarvis                  # chat
    python -m jarvis -c "كم الساعة"   # one message
    python -m jarvis --doctor         # health report
    python -m jarvis --heal           # repair everything that can be repaired
    python -m jarvis --rollback       # undo code repairs made by the healer
"""
from __future__ import annotations

import argparse
import sys
import time

from .core import Jarvis
from .text import utf8_console

EXIT = {"exit", "quit", "bye jarvis", "خروج", "اطلع", "سكر", "مع السلامة جارفيس"}
BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
"""


def _print_checks(j: Jarvis) -> None:
    for c in j.healer.health_check():
        mark = "OK  " if c.ok and not c.warn else ("WARN" if c.ok or c.warn else "FAIL")
        print(f"  [{mark}] {c.name}: {c.detail}")


def chat(j: Jarvis) -> None:
    print(BANNER)
    for name, status in j.router.status():
        print(f"  brain {name}: {status}")
    for note in j.startup_notes:
        print(f"  🔧 {note}")
    print(f"\n{j.config['name']}: مرحباً {j.config['user_title']}، كيف أقدر أخدمك؟ (اكتب «مساعدة» أو help، و«خروج» للخروج)\n")
    crashes: list[float] = []
    while True:
        for note in j.pending_notifications():
            print(f"{j.config['name']} › {note}")
        try:
            text = input("أنت › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in EXIT:
            print(f"{j.config['name']}: في أمان الله.")
            break
        try:
            reply = j.handle(text)
            print(f"{j.config['name']} [{reply.source}] › {reply.text}\n")
            if reply.source == "skill:ai_control" and j.ai_setup.thread and j.ai_setup.thread.is_alive():
                while j.ai_setup.thread.is_alive():          # show progress until the setup finishes
                    for note in j.pending_notifications():
                        print(f"{j.config['name']} › {note}")
                    j.ai_setup.thread.join(1)
                for note in j.pending_notifications():
                    print(f"{j.config['name']} › {note}")
        except Exception as exc:  # supervisor: keep the loop alive, heal, carry on
            crashes = [t for t in crashes if time.time() - t < 60] + [time.time()]
            j.healer.record("cli", exc)
            j.healer.heal_all()
            print(f"{j.config['name']}: حصل عطل غير متوقع ({exc}). تم تسجيله وإصلاح ما يمكن.\n")
            if len(crashes) >= 5:
                print("Too many crashes in one minute; stopping. See ~/.jarvis/logs/errors.log")
                break


def voice_chat(j: Jarvis) -> None:
    """Hands-free: listen -> answer -> speak, until you say an exit word."""
    print(j.voice.status())
    print("🎤 تكلم… (قل «خروج» للإنهاء / say 'exit' to stop)\n")
    while True:
        try:
            text = j.voice.listener.listen()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"🎤 ما سمعتك: {exc}")
            time.sleep(1)
            continue
        print(f"أنت › {text}")
        if text.strip().lower() in EXIT:
            j.voice.speaker.speak("في أمان الله")
            break
        reply = j.handle(text)
        print(f"{j.config['name']} › {reply.text}\n")
        try:
            j.voice.speaker.speak(reply.text)
        except Exception as exc:
            print(f"🔇 {exc}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jarvis", description="Your personal self-learning, self-healing assistant")
    p.add_argument("-c", "--command", help="send one message and print the reply")
    p.add_argument("--doctor", action="store_true", help="print a health report")
    p.add_argument("--heal", action="store_true", help="repair everything that can be repaired")
    p.add_argument("--rollback", nargs="?", const="", metavar="SKILL", help="undo code repairs (optionally one skill)")
    p.add_argument("--voice", action="store_true", help="talk to Jarvis with your voice")
    p.add_argument("--say", metavar="TEXT", help="speak a sentence aloud")
    p.add_argument("--home", help="data folder (default ~/.jarvis or $JARVIS_HOME)")
    args = p.parse_args(argv)
    utf8_console()

    j = Jarvis(home=args.home)
    try:
        if args.doctor:
            _print_checks(j)
        elif args.heal:
            notes = j.healer.heal_all()
            for n in (j.startup_notes + notes) or ["nothing to repair"]:
                print(f"  🔧 {n}")
            _print_checks(j)
        elif args.rollback is not None:
            done = j.healer.rollback(args.rollback or None)
            print("\n".join(done) if done else "no code backups to restore")
        elif args.say:
            print(j.voice.speaker.speak(args.say))
        elif args.voice:
            voice_chat(j)
        elif args.command:
            print(j.handle(args.command).text)
        else:
            chat(j)
    finally:
        j.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
