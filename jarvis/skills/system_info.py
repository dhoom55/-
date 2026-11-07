import os
import platform
import shutil
import sys

NAME = "system_info"
PATTERNS = [r"(حاله الجهاز|معلومات الجهاز|حاله النظام|system status|system info|computer status)"]
TESTS = ["حالة النظام", "system status"]


def _memory() -> str:
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0])
        total, avail = info["MemTotal"] / 1048576, info["MemAvailable"] / 1048576
        return f"{avail:.1f}/{total:.1f} GB"
    except (OSError, KeyError, ValueError):
        return "?"


def handle(text, match, jarvis):
    disk = shutil.disk_usage(jarvis.config.home)
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    facts = {
        "os": f"{platform.system()} {platform.release()}",
        "python": sys.version.split()[0],
        "cpus": os.cpu_count(),
        "load": f"{load:.2f}",
        "ram": _memory(),
        "disk": f"{disk.free / 1e9:.1f}/{disk.total / 1e9:.1f} GB",
    }
    ar = (f"النظام: {facts['os']} | بايثون {facts['python']} | المعالجات: {facts['cpus']} "
          f"(الحمل {facts['load']}) | الذاكرة المتاحة: {facts['ram']} | المساحة الحرة: {facts['disk']}")
    en = (f"System: {facts['os']} | Python {facts['python']} | CPUs: {facts['cpus']} "
          f"(load {facts['load']}) | free RAM: {facts['ram']} | free disk: {facts['disk']}")
    return jarvis.say(ar, en, text)
