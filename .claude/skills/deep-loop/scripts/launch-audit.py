# -*- coding: utf-8 -*-
"""deep-loop 발동 형태 전수 측정 — rationale G1 예측의 재측정 자.

발동(`Launching skill: deep-loop` 또는 /deep-loop) 마다:
  head   = 첫 보이는 텍스트 전 tool_use 수 (A = 0~4 머리 먼저 · B = 5 이상 또는 텍스트 없이 도구만)
  alarm  = 그 세션 어디든 silent_turn_reminder / batching_reminder_sent 첨부가 있는가
사용: py -3 launch-audit.py [--since 2026-09-14] [--exclude <세션id 앞 8자>]
"""
import json, sys, glob, os, re, argparse, collections

ap = argparse.ArgumentParser()
ap.add_argument("--since", default="")
ap.add_argument("--exclude", default="")
# 기본 = 지금 폴더의 트랜스크립트 폴더(Claude Code 는 경로의 영숫자 아닌 글자를 '-' 로 바꿔 폴더 이름을 만든다)
ap.add_argument("--dir", default=os.path.expanduser("~/.claude/projects/" + re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())))
a = ap.parse_args()
sys.stdout.reconfigure(encoding="utf-8")
ALARMS = ('"silent_turn_reminder"', '"batching_reminder_sent"')


def is_prompt(e):
    if e.get("type") != "user" or e.get("isMeta"):
        return False
    c = e.get("message", {}).get("content")
    if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
        return False
    txt = c if isinstance(c, str) else " ".join(b.get("text", "") for b in c or [] if isinstance(b, dict))
    return not txt.startswith("Base directory for this skill:")  # 스킬 본문 주입은 프롬프트가 아니다


def is_launch(e):
    """Skill 도구의 tool_result 가 정확히 'Launching skill: deep-loop' 인 것만. 측정 출력에 그 문자열이 찍힌 것은 제외."""
    c = e.get("message", {}).get("content")
    if isinstance(c, str):
        return c.lstrip().startswith("<command-name>/deep-loop") and not e.get("isMeta")
    for b in c or []:
        if isinstance(b, dict) and b.get("type") == "tool_result":
            v = b.get("content")
            v = v if isinstance(v, str) else " ".join(x.get("text", "") for x in v or [] if isinstance(x, dict))
            if v.strip() == "Launching skill: deep-loop":
                return True
    return False


rows = []
for f in glob.glob(os.path.join(a.dir, "*.jsonl")):
    sid = os.path.basename(f)[:8]
    if a.exclude and sid == a.exclude:
        continue
    lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
    att = [l for l in lines if '"type":"attachment"' in l or '"type": "attachment"' in l]
    alarm = any(k in l for l in att for k in ALARMS)
    snap = [l for l in att if '"prompt_snapshot"' in l]
    # 시스템 프롬프트 변형: D = '# Delivering work' 절 있음 · n = 스냅샷은 있는데 절 없음 · ? = 스냅샷 없음(09-10 이전)
    sp = "?" if not snap else ("D" if "# Delivering work" in snap[0] else "n")
    ev = []
    for l in lines:
        try:
            ev.append(json.loads(l))
        except Exception:
            pass
    for i, e in enumerate(ev):
        if e.get("type") != "user" or e.get("timestamp", "") < a.since:
            continue
        if not is_launch(e):
            continue
        tools, head = 0, -1
        for e2 in ev[i + 1:]:
            if is_prompt(e2):
                break
            if e2.get("type") != "assistant":
                continue
            for b in e2["message"].get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    tools += 1
                elif b.get("type") == "text" and b["text"].strip() and head == -1:
                    head = tools
        mode = "A" if 0 <= head <= 4 else ("B" if head > 4 or tools > 4 else "?")
        rows.append((e["timestamp"][:16], sid, mode, head, tools, alarm, sp))

rows.sort()
for r in rows:
    print(f"{r[0]} {r[1]} {r[2]} head={r[3]:>3} tools={r[4]:>3} alarm={int(r[5])} prompt={r[6]}")
c = collections.Counter((r[5], r[2]) for r in rows)
print(f"알림 세션: A {c[(True,'A')]} · B {c[(True,'B')]} | 비알림 세션: A {c[(False,'A')]} · B {c[(False,'B')]} (발동 단위)")
