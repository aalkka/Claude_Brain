# -*- coding: utf-8 -*-
"""**vault-baseline** — 볼트 개혁 전·후를 같은 자로 잰다 (2026-10-29 · 로드맵 R1 · R10 에서 다시).

  py -3 3_시스템/_eval/vault-baseline.py --topic 기초물리학실험,기물실           재고 저장
  py -3 3_시스템/_eval/vault-baseline.py --compare 3_시스템/_index/baseline/2026-10-29.json   지금과 비교

잰 것(설계안 §15.1): 탐색기에 보이는 폴더(사람 공간·시스템·색인) · 사람 공간 최대 깊이 · 주제 흩어짐(그 이름이 든 폴더 수와 층)
· 위키링크 중 못 찾는 것(근사 — 이름·경로·뒤쪽 일치·./ ../ 로 못 찾음, 코드 블록 제외) · 받은함 머무름 · 휴지통 · 장부 행위 수.
결과 = `3_시스템/_index/baseline/<날짜>.json`(파생물 · git 제외) — 숫자는 로드맵 노트에도 옮겨 적는다.
찾기 과제 시간은 사람이 잰다(이 대본 밖).
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

VAULT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYSTEM, INDEX, LMS = "3_시스템", "1_수집/_색인", "1_수집/_lms"
SKIP = {".git", ".obsidian", ".trash", "node_modules", "__pycache__"}
WIKI = re.compile(r"!?\[\[([^\[\]|#\n]+)")
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`")


def rel(p):
    r = os.path.relpath(p, VAULT).replace("\\", "/")
    return "" if r == "." else r


def measure(topics):
    out = {"date": dt.date.today().isoformat()}
    # 1. 탐색기에 보이는 폴더 — 옵시디언은 점 폴더만 숨긴다(userIgnoreFilters 는 검색·그래프만 뺀다)
    dirs = []
    for dp, dns, _ in os.walk(VAULT):
        dns[:] = [d for d in dns if not d.startswith(".")]
        r = rel(dp)
        if r:
            dirs.append(r)
    group = collections.Counter()
    for d in dirs:
        group["시스템" if d.startswith(SYSTEM) else "색인" if d.startswith(INDEX) else "lms" if d.startswith(LMS) else "사람"] += 1
    people = [d for d in dirs if not d.startswith((SYSTEM, INDEX, LMS))]
    out["폴더"] = {"보임": len(dirs), **dict(group)}
    out["사람_최대깊이"] = max((d.count("/") + 1 for d in people), default=0)
    # 2. 주제 흩어짐 — 이름(별칭 포함)이 든 폴더 수와 꼭대기 층
    out["주제"] = {}
    for t in topics:
        names = [x.strip() for x in t.split(",") if x.strip()]
        hit = [d for d in people if any(n in d for n in names)]
        out["주제"][names[0]] = {"폴더": len(hit), "층": dict(collections.Counter(d.split("/")[0] for d in hit))}
    # 3. 못 찾는 위키링크(근사)
    files = []
    for dp, dns, fns in os.walk(VAULT):
        dns[:] = [d for d in dns if d not in SKIP]
        files += [rel(os.path.join(dp, f)) for f in fns]
    low = {f.lower() for f in files}
    noext = {f[:-3].lower() for f in files if f.lower().endswith(".md")}
    base = collections.Counter()
    for f in files:
        b = f.rsplit("/", 1)[-1].lower()
        base[b] += 1
        if b.endswith(".md"):
            base[b[:-3]] += 1
    total = broken = 0
    notes = set()
    for f in files:
        if not f.endswith(".md") or f.startswith((SYSTEM + "/_index/", INDEX + "/")):
            continue
        try:
            text = open(os.path.join(VAULT, f), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        text = INLINE.sub("", FENCE.sub("", text))
        d = f.rsplit("/", 1)[0] if "/" in f else ""
        for m in WIKI.finditer(text):
            t = m.group(1).strip().replace("\\", "/")
            if not t:
                continue
            total += 1
            tl = t.lower()
            if t.startswith(("./", "../")):
                j = os.path.normpath(os.path.join(d, t)).replace("\\", "/").lower()
                ok = j in low or j in noext
            elif "/" in t:
                ok = tl in low or tl in noext or any(x.endswith("/" + tl) or x.endswith("/" + tl + ".md") for x in low)
            else:
                ok = base.get(tl, 0) > 0
            if not ok:
                broken += 1
                notes.add(f)
    out["링크"] = {"위키링크": total, "못찾음": broken, "그런노트": len(notes)}
    # 4. 받은함 · 휴지통 · 장부
    inbox = os.path.join(VAULT, "1_수집", "받은함")
    waiting = []
    if os.path.isdir(inbox):
        for dp, dns, fns in os.walk(inbox):
            dns[:] = [x for x in dns if not x.startswith("_")]          # _ 칸은 빼고
            waiting += [os.path.getmtime(os.path.join(dp, f)) for f in fns if not f.startswith(".")]
    now = dt.datetime.now().timestamp()
    out["받은함"] = {"건": len(waiting), "가장오래된_일": int((now - min(waiting)) / 86400) if waiting else 0}
    tr = os.path.join(VAULT, ".trash")
    tf = [os.path.join(dp, f) for dp, _, fns in os.walk(tr) for f in fns] if os.path.isdir(tr) else []
    out["휴지통"] = {"파일": len(tf), "MB": round(sum(os.path.getsize(x) for x in tf) / 1e6, 1)}
    ops = os.path.join(VAULT, "3_시스템", "ledger", "ops.jsonl")
    out["장부_행위"] = sum(1 for _ in open(ops, encoding="utf-8")) if os.path.exists(ops) else 0
    return out


def flat(d, pre=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from flat(v, pre + k + ".")
        else:
            yield pre + k, v


def main():
    ap = argparse.ArgumentParser(description="볼트 개혁 기준선 — 재고 저장, 또는 저장본과 비교")
    ap.add_argument("--topic", action="append", default=[], help="주제 이름(쉼표로 별칭) — 여러 번 줄 수 있음")
    ap.add_argument("--compare", help="예전 기준선 JSON — 지금과 나란히")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    now = measure(a.topic)
    if a.compare:
        old = json.load(open(a.compare, encoding="utf-8"))
        o, n = dict(flat(old)), dict(flat(now))
        for k in sorted(set(o) | set(n)):
            if o.get(k) != n.get(k):
                print("%s: %s → %s" % (k, o.get(k, "-"), n.get(k, "-")))
        return 0
    for k, v in flat(now):
        print("%s: %s" % (k, v))
    if not a.no_save:
        p = os.path.join(VAULT, "3_시스템", "_index", "baseline", now["date"] + ".json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(now, f, ensure_ascii=False, indent=1)
        print("저장: %s" % rel(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
