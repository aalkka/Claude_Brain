#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""주간 점검의 측정을 한 번에 — weekly-review 스킬이 부른다(11-02 · 실행당 도구 평균 28회가 대부분 재는 일이었다).

읽기 전용(결과 파일 덧붙이기만). 판정·정리·승인은 스킬과 사람 몫이다.

  py -3 3_시스템/weekly.py [--save] [--no-eval]
    --save     _eval/results-weekly.md 에 주차별로 덧붙인다
    --no-eval  골든셋 재측정을 건너뛴다(무겁거나 모델이 없을 때)
"""
import datetime as dt
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drift  # noqa: E402
import moc as moc_mod  # noqa: E402
import roles  # noqa: E402
import skillstat  # noqa: E402

VAULT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "_eval", "results-weekly.md")
GOLDEN = os.path.join(HERE, "_eval", "golden.jsonl")
LOG = os.path.join(HERE, "_index", "core-gate.log")
CORE = ["3_시스템/hooks/", "3_시스템/search.py", "CLAUDE.md", "3_시스템/conventions.md", ".claude/settings.json", ".obsidian/plugins/"]
TYPES = {"semantic", "episodic", "procedural", "decision", "moc", "incident"}
KEYS = {"type", "title", "created", "updated", "tags", "links", "status", "confidence", "source", "sensitive", "주제", "aliases", "마감", "단계", "의도", "author", "보냄", "결과물", "저장소", "가지", "session"}
ALWAYS = {"MOC", "recent", "open-loops", "profile", "설계노트", "사용자설명서"}   # 상시 갱신 파일은 created 없어도 정상
TAGS = ["ASK", "TOKEN-ALLOW", "TOKEN-DENY", "TOKEN-OTHERSESSION", "TOKEN-EXPIRED", "TOKEN-NOSESSION", "TOKEN-BINDFAIL", "GATE-BROKEN", "OPS-GUARD"]


def git(*a):
    r = subprocess.run(["git", "-C", VAULT, "-c", "core.quotepath=false", *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip()


def run(args, timeout):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env, cwd=VAULT)
    except (OSError, subprocess.SubprocessError) as e:
        return f"미실행: {type(e).__name__}"
    return (r.stdout or r.stderr).strip()


def core_gate():
    log = git("log", "--since=7 days ago", "--format=%h %cs %s", "--", *CORE)
    lines = [x for x in log.split("\n") if x]
    anon = [x for x in lines if " session:" in x]
    out = [f"- 코어 변경 커밋 {len(lines)} · 그중 `session:` {len(anon)}"]
    for x in anon[:12]:
        h, d = x.split()[:2]
        out.append(f"  - {h} {d} — 근거 후보: {evidence(d)}")
    cut = (dt.datetime.now() - dt.timedelta(days=7)).strftime("%Y-%m-%d")
    cnt, targets = {}, []
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8", errors="replace") as h:
            for ln in h:
                if ln[:10] < cut:
                    continue
                tag = next((t for t in TAGS if f" {t} " in ln), "태그 없음")
                cnt[tag] = cnt.get(tag, 0) + 1
                if tag.startswith("TOKEN-"):
                    targets.append(ln.split(tag, 1)[1].strip()[:60])
    total = sum(cnt.values())
    out.append(f"- 게이트 발동 {total} · " + " · ".join(f"{k} {v}" for k, v in sorted(cnt.items())))
    if cnt.get("GATE-BROKEN"):
        out.append("- ⚠ **GATE-BROKEN** — 판정부가 사라져 게이트가 죽은 상태")
    if lines and not total:
        out.append("- ⚠ 코어 변경이 있는데 발동 0 — 게이트가 죽었거나 우회됐다")
    if targets:
        out.append("- TOKEN 대상: " + " · ".join(sorted(set(targets))[:8]))
    return out


def evidence(day):
    """익명 코어 커밋의 근거 문서 — 그 날짜(전후 1일)의 세션노트·결정·incident"""
    d = dt.date.fromisoformat(day)
    days = {(d + dt.timedelta(days=i)).isoformat() for i in (-1, 0, 1)}
    hits = []
    for base in (roles.path("sessions"), roles.path("decisions"), roles.path("system") + "/_ref"):
        a = os.path.join(VAULT, base)
        for f in os.listdir(a) if os.path.isdir(a) else ():
            if f.endswith(".md") and (any(x in f for x in days) or file_created(os.path.join(a, f)) in days):
                hits.append(f[:-3])
    return " · ".join(hits[:3]) if hits else "**못 찾음 — 사후 검토**"


def file_created(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as h:
            m = re.search(r"^created:\s*(\S+)", h.read(600), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def frontmatter():
    yaml_bad, bad_type, bad_key, old_key, no_created = [], [], {}, 0, []
    for base in ("2_지식", "3_시스템/_ref"):
        for dp, _, fs in os.walk(os.path.join(VAULT, base)):
            for f in fs:
                if not f.endswith(".md"):
                    continue
                p = os.path.join(dp, f)
                try:
                    with open(p, encoding="utf-8-sig", errors="replace") as h:
                        lines = h.read(8000).split("\n")
                except OSError:
                    continue
                if not lines or lines[0].strip() != "---":
                    continue
                keys, bad = set(), False
                for ln in lines[1:]:
                    if ln.strip() == "---":
                        break
                    m = re.match(r"^([^\s:#-][^:]*):[ \t]*(.*)$", ln)
                    if not m:
                        continue
                    k, v = m.group(1), m.group(2)
                    keys.add(k)
                    if v.startswith('"'):
                        bad = bad or not re.fullmatch(r'"[^"]*"\s*', v)
                    elif not re.match(r'[\["{]', v) and re.search(r":[ \t]", v):
                        bad = True
                    if k == "type" and v.strip() and v.strip() not in TYPES:
                        bad_type.append(f"{f}({v.strip()})")
                if bad:
                    yaml_bad.append(drift.rel(p))
                for k in keys - KEYS:
                    if k == "importance":
                        old_key += 1
                    else:
                        bad_key[k] = bad_key.get(k, 0) + 1
                if "created" not in keys and f[:-3] not in ALWAYS:
                    no_created.append(f)
    out = [f"- YAML 위반 {len(yaml_bad)} · 스키마 밖 type {len(bad_type)} · 옛 키 importance {old_key} · created 없음 {len(no_created)}"]
    if yaml_bad:
        out.append("  - YAML: " + " · ".join(yaml_bad[:8]))
    if bad_type:
        out.append("  - type: " + " · ".join(bad_type[:8]))
    if bad_key:
        out.append("  - 이물 키: " + " · ".join(f"{k} {v}" for k, v in sorted(bad_key.items(), key=lambda kv: -kv[1])[:8]))
    return out


def dir_size(a):
    total, n = 0, 0
    for dp, _, fs in os.walk(a):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return total, n


def health():
    notes = 0
    for d in roles.group("knowledge_notes"):
        for _, _, fs in os.walk(os.path.join(VAULT, d)):
            notes += sum(f.endswith(".md") for f in fs)
    t1 = {n: os.path.getsize(os.path.join(VAULT, "2_지식", n)) for n in ("recent.md", "open-loops.md")}
    size, _ = dir_size(os.path.join(HERE, "_index"))
    work = os.path.join(HERE, "_index", "work")
    wn = len(os.listdir(work)) if os.path.isdir(work) else 0
    last = git("log", "-1", "--format=%cr")
    mem = dir_size(os.path.join(HERE, "_claude-memory"))
    out = [f"- 노트 {notes} · recent {t1['recent.md']}B · open-loops {t1['open-loops.md']}B(6KB까지) · 기억 색인 {os.path.getsize(os.path.join(HERE, '_claude-memory', 'MEMORY.md'))}B · 기억 {mem[1]}개",
           f"- _index {size // 1048576}MB(200MB 넘으면 정리 제안) · work {wn}개(50개 넘으면) · 마지막 커밋 {last}"]
    return out


def loops():
    with open(os.path.join(VAULT, "2_지식", "open-loops.md"), encoding="utf-8") as h:
        t = h.read()
    sect, form, long_ = False, 0, 0
    for ln in t.split("\n"):
        if ln.startswith("## "):
            sect = True
        elif sect and ln.startswith("- "):
            if not re.match(r"- \[[ x]\]", ln):
                form += 1
            if len(ln) > 300:
                long_ += 1
    return [f"- 형식 위반 {form} · 300자 넘는 항목 {long_}"]


def incidents():
    cut = dt.datetime.now().timestamp() - 7 * 86400
    a = os.path.join(HERE, "_ref")
    with open(moc_mod.MOC, encoding="utf-8") as h:
        moc = h.read()
    new = [f[:-3] for f in os.listdir(a) if f.startswith("incident-") and os.path.getmtime(os.path.join(a, f)) >= cut]
    miss = [n for n in new if f"[[{n}" not in moc]
    out = [f"- 7일 안 incident {len(new)} · MOC 미반영 {len(miss)}"]
    out += [f"  - {n}" for n in miss[:10]]
    return out


def drift_part():
    rows = drift.all_rows()
    c = {}
    for k, _, _ in rows:
        c[k] = c.get(k, 0) + 1
    out = ["- " + (" · ".join(f"{k} {v}" for k, v in c.items()) if rows else "어긋남 0")]
    out += [f"  - {k} {w}: {t}" for k, w, t in rows[:25]]
    if len(rows) > 25:
        out.append(f"  - … 외 {len(rows) - 25}(전체 = `py -3 3_시스템/drift.py`)")
    es = moc_mod.entries(moc_mod.read_moc())
    long_ = [x for x in moc_mod.read_moc() if x.startswith("- ") and len(x) > moc_mod.LIMIT]
    lost = [n for n, _ in es if n not in moc_mod.md_files() and n != "open-loops"]
    out.append(f"- MOC 등재 {len(es)} · 150자 넘음 {len(long_)} · 못 찾는 링크 {len(lost)}")
    hp = run(["py", "-3", os.path.join(HERE, "_eval", "hardpaths.py")], 120).split("\n")[0]
    out.append(f"- 코드의 {hp}")
    return out


def skills():
    rows = skillstat.rows(60)
    dead = [r for r in rows if r["최근"] == 0 and r["대본"] == 0]
    out = ["- 많이 쓴 순(60일): " + " · ".join(f"{r['이름']} {r['최근']}" for r in rows[:6] if r["최근"])]
    out.append(f"- 60일 호출·대본 0({len(dead)}): " + " · ".join(f"{r['이름']}({r['마지막']})" for r in dead))
    return out


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    today = dt.date.today().isoformat()
    parts = [f"## {today} — weekly.py", "", "### 코어 게이트"] + core_gate()
    parts += ["", "### 어긋남·MOC"] + drift_part()
    parts += ["", "### 프론트매터"] + frontmatter()
    parts += ["", "### 헬스"] + health()
    parts += ["", "### open-loops"] + loops()
    parts += ["", "### incident"] + incidents()
    parts += ["", "### 스킬 사용"] + skills()
    if "--no-eval" not in argv and os.path.exists(GOLDEN):
        parts += ["", "### 골든셋", "```", run(["py", "-3", os.path.join(HERE, "search.py"), "--eval", GOLDEN, "--k", "8"], 900)[-800:], "```"]
    elif not os.path.exists(GOLDEN):
        parts += ["", "### 골든셋", "- 골든 파일 없음 — `_eval/measure.md` 절차로 작성 권유"]
    parts += ["", "### 토큰·출력 품질", "```", run(["py", "-3", os.path.join(HERE, "tokens.py"), "--n", "10", "--tools", "--batch", "--quality"], 300)[-5000:], "```"]
    text = "\n".join(parts) + "\n"
    print(text)
    if "--save" in argv:
        with open(OUT, "a", encoding="utf-8", newline="") as h:
            h.write("\n" + text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
