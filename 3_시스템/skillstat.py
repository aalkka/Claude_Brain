#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""스킬이 실제로 쓰이는지 대화 기록에서 잰다(11-02 · 안 쓰는 스킬이 쌓여도 알 길이 없었다).

  py -3 3_시스템/skillstat.py [--days 60]        볼트 스킬 전부: 호출(전체·최근) · 마지막 · 딸린 대본 실행(최근)

호출 = Skill 도구 + 사용자가 친 /이름. 대본 = 스킬 없이 직접 부른 경우까지 보려고 따로 센다(search 는 호출 0 · search.py 162회였다).
"""
import datetime as dt
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
ROOT = os.path.expanduser("~/.claude/projects")
SKILLS = os.path.join(VAULT, ".claude", "skills")
CMD = re.compile(r"<command-name>/?([^<]+)</command-name>")
# 스킬이 감싼 대본 — 이것을 직접 부르면 스킬 없이도 그 일은 하는 것이다
SCRIPTS = {"pdf-ingest": "ingest.py", "defuddle": "defuddle parse",
           "eye": "eye.py", "module-forge:check": "module-forge/scripts/check.py", "canvas": "canvas-build.py",
           "session-record": "record.py", "weekly-review": "weekly.py"}


def local_skills():
    out = []
    for p in glob.glob(os.path.join(SKILLS, "**", "SKILL.md"), recursive=True):
        r = os.path.relpath(os.path.dirname(p), SKILLS).replace(os.sep, "/")
        out.append(r.replace("/skills/", ":"))
    return sorted(out)


def scan(days):
    cut = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    calls, recent, last, runs = {}, {}, {}, {}
    def hit(n, ts):
        calls[n] = calls.get(n, 0) + 1
        if ts >= cut:
            recent[n] = recent.get(n, 0) + 1
        last[n] = max(last.get(n, ""), ts)
    for f in glob.glob(ROOT + "/**/*.jsonl", recursive=True):
        if "subagents" in f.replace("\\", "/"):
            continue
        with open(f, encoding="utf-8", errors="replace") as h:
            for line in h:
                has_s = '"Skill"' in line or "command-name" in line
                has_r = '"Bash"' in line or '"PowerShell"' in line
                if not has_s and not has_r:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                ts = o.get("timestamp", "")[:10]
                c = (o.get("message") or {}).get("content")
                if isinstance(c, str):
                    if o.get("type") == "user":
                        for n in CMD.findall(c):
                            hit(n.strip(), ts)
                    continue
                if not isinstance(c, list):
                    continue
                for b in c:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use" and b.get("name") == "Skill":
                        hit((b.get("input") or {}).get("skill", "?"), ts)
                    elif b.get("type") == "tool_use" and b.get("name") in ("Bash", "PowerShell") and ts >= cut:
                        cmd = str((b.get("input") or {}).get("command", ""))
                        for s, frag in SCRIPTS.items():
                            if frag in cmd:
                                runs[s] = runs.get(s, 0) + 1
                    elif b.get("type") == "text" and o.get("type") == "user":
                        for n in CMD.findall(b.get("text", "")):
                            hit(n.strip(), ts)
    return calls, recent, last, runs


def rows(days=60):
    calls, recent, last, runs = scan(days)
    out = [dict(이름=s, 호출=calls.get(s, 0), 최근=recent.get(s, 0), 마지막=last.get(s, "-"), 대본=runs.get(s, 0)) for s in local_skills()]
    return sorted(out, key=lambda r: (-(r["최근"]), -r["호출"], -r["대본"]))


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 60
    for r in rows(days):
        flag = " · 안 쓰임" if r["최근"] == 0 and r["대본"] == 0 else ""
        print(f"{r['이름']:<30} 호출 {r['호출']:>3} · 최근{days}일 {r['최근']:>3} · 마지막 {r['마지막']} · 대본 {r['대본']:>3}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
