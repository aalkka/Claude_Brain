# -*- coding: utf-8 -*-
"""**공휴일 표** — 구글 «대한민국 공휴일» 달력에서 공휴일만 받아 일정 폴더의 `공휴일.md` JSON 블록에 둔다(볼트 개혁 · 캘린더 brain-calendar 가 읽음).

왜 받기: 음력 명절·대체공휴일·선거일을 해마다 손으로 적는 일을 없앤다. 표로 두는 까닭 = 캘린더는 폰에서도 돌아 네트워크에 기대지 않고, 빠진 날은 사람이 고칠 수 있다.

  py -3 3_시스템/holidays.py [--if-old 30] [--dry] [--ics 파일]
    --if-old N  표를 받은 지 N일 안이면 받지 않는다(주간 점검이 부름)
    --ics 파일  달력 파일을 네트워크 대신(시험)

받기만(GET 하나 · 글자로만 읽음). 달력의 기념일(어버이날 등)은 뺀다. «손으로» 칸(임시공휴일처럼 사람이 적은 날)은 다시 받아도 남는다. 못 받으면 표를 그대로 둔다.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roles  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://calendar.google.com/calendar/ical/ko.south_korea%23holiday%40group.v.calendar.google.com/public/basic.ics"
NAME = "공휴일.md"
BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.S)


def parse_ics(text):
    """달력 글자 → {날짜: 이름} — 공휴일만(설명 칸이 «공휴일»으로 시작) · 여러 날짜 일정은 펼침 · 같은 날 둘이면 이름을 잇는다."""
    text = re.sub(r"\r?\n[ \t]", "", text)                     # 접힌 줄 펴기(RFC 5545)
    out = {}
    for ev in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        def field(key):
            m = re.search(r"^%s(?:;[^:\n]*)?:(.*)$" % key, ev, re.M)
            return m.group(1).strip() if m else ""
        if not field("DESCRIPTION").startswith("공휴일"):
            continue
        s, e = field("DTSTART"), field("DTEND")
        if not re.fullmatch(r"\d{8}", s):
            continue
        name = field("SUMMARY").replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").strip()
        d0 = dt.date(int(s[:4]), int(s[4:6]), int(s[6:]))
        d1 = dt.date(int(e[:4]), int(e[4:6]), int(e[6:])) if re.fullmatch(r"\d{8}", e) else d0 + dt.timedelta(days=1)
        for k in range(max(1, (d1 - d0).days)):
            day = (d0 + dt.timedelta(days=k)).isoformat()
            if name and name not in out.get(day, ""):
                out[day] = out[day] + " · " + name if day in out else name
    return out


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 BrainHolidays/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(2_000_000).decode("utf-8", "replace")


def read_table(path):
    try:
        text = open(path, encoding="utf-8").read()
        m = BLOCK.search(text)
        created = re.search(r"^created:\s*(\S+)", text, re.M)
        return (json.loads(m.group(1)) if m else {}), (created.group(1) if created else None)
    except (OSError, ValueError):
        return {}, None


def write_table(path, table, created):
    today = dt.date.today().isoformat()
    body = ["---", "title: 공휴일 표", "created: " + (created or today), "updated: " + today, "tags: [일정, 공휴일, 생성파일]", "주제:", "aliases: []", "links: []",
            "status: active", "source: claude", "---", "# 공휴일",
            "",
            "> 캘린더가 읽는 표. `공휴일` 칸은 `py -3 3_시스템/holidays.py`(구글 «대한민국 공휴일» 달력 · 기념일 뺌)가 다시 쓴다. 빠진 날·임시공휴일은 `손으로` 칸에 `\"2027-01-02\": \"임시공휴일\"` 처럼 적으면 다시 받아도 남는다.",
            "",
            "```json", json.dumps(table, ensure_ascii=False, indent=1), "```", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(body))
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="holidays", description="공휴일 표 받기")
    ap.add_argument("--if-old", type=int, help="받은 지 이 날 수 안이면 받지 않음")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--ics", help="달력 파일(시험)")
    a = ap.parse_args(argv)
    path = os.path.join(VAULT, *roles.path("schedule", NAME).split("/"))
    old, created = read_table(path)
    today = dt.date.today()
    if a.if_old is not None and old.get("받은 날"):
        try:
            if (today - dt.date.fromisoformat(old["받은 날"])).days < a.if_old:
                print("공휴일 표 %s 받음 — 건너뜀" % old["받은 날"])
                return 0
        except ValueError:
            pass
    try:
        text = open(a.ics, encoding="utf-8").read() if a.ics else fetch()
    except OSError as e:
        print("공휴일 달력을 못 받음(%s) — 표는 그대로" % (getattr(e, "reason", None) or e))
        return 1
    got = parse_ics(text)
    if len(got) < 10:       # 달력 꼴이 바뀌었거나 다른 응답 — 표를 비우지 않는다
        print("공휴일 %d개뿐 — 달력 꼴이 바뀐 듯 · 표는 그대로" % len(got))
        return 1
    keep = "%d-01-01" % (today.year - 1)
    table = {"받은 날": today.isoformat(), "공휴일": {k: got[k] for k in sorted(got) if k >= keep}, "손으로": old.get("손으로") or {}}
    print("공휴일 %d개 · %s ~ %s%s" % (len(table["공휴일"]), min(table["공휴일"]), max(table["공휴일"]), " (미리 보기)" if a.dry else ""))
    if not a.dry:
        write_table(path, table, created)
    return 0


if __name__ == "__main__":
    sys.exit(main())
