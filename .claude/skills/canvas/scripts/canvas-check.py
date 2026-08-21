#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""JSON Canvas 기하·스키마 검사기.
사용: python 3_시스템/canvas-check.py "2_지식/_canvas/x.canvas"
좌표를 눈으로 찍지 않기 위한 도구. 겹침·그룹포함·행열정렬·20스냅·스키마·엣지관통을 본다.
엣지 관통은 직선 근사(Obsidian은 베지어) — 참고치.
"""
import json, sys, itertools, os

SNAP = 20

def rect(n): return (n["x"], n["y"], n["x"]+n["width"], n["y"]+n["height"])

def overlap(a, b, pad=0):
    ax1,ay1,ax2,ay2 = rect(a); bx1,by1,bx2,by2 = rect(b)
    return not (ax2+pad <= bx1 or bx2+pad <= ax1 or ay2+pad <= by1 or by2+pad <= ay1)

def inside(inner, outer):
    ix1,iy1,ix2,iy2 = rect(inner); ox1,oy1,ox2,oy2 = rect(outer)
    return ox1 <= ix1 and oy1 <= iy1 and ix2 <= ox2 and iy2 <= oy2

CONTENT_KEY = {"text":"text", "file":"file", "link":"url", "group":None}

def seg_rect_hit(p, q, r):
    """선분 p-q 가 사각형 r 내부를 지나는가 (끝점이 r 안이면 제외)."""
    x1,y1,x2,y2 = rect(r)
    def code(pt):
        c = 0
        if pt[0] < x1: c |= 1
        elif pt[0] > x2: c |= 2
        if pt[1] < y1: c |= 4
        elif pt[1] > y2: c |= 8
        return c
    a, b = list(p), list(q)
    ca, cb = code(a), code(b)
    for _ in range(32):
        if not (ca | cb): return True
        if ca & cb: return False
        c = ca or cb
        if c & 8:   x = a[0] + (b[0]-a[0]) * (y2-a[1]) / (b[1]-a[1]); y = y2
        elif c & 4: x = a[0] + (b[0]-a[0]) * (y1-a[1]) / (b[1]-a[1]); y = y1
        elif c & 2: y = a[1] + (b[1]-a[1]) * (x2-a[0]) / (b[0]-a[0]); x = x2
        else:       y = a[1] + (b[1]-a[1]) * (x1-a[0]) / (b[0]-a[0]); x = x1
        if c == ca: a = [x,y]; ca = code(a)
        else:       b = [x,y]; cb = code(b)
    return False

def anchor(n, side):
    x1,y1,x2,y2 = rect(n); cx,cy = (x1+x2)/2, (y1+y2)/2
    return {"top":(cx,y1),"bottom":(cx,y2),"left":(x1,cy),"right":(x2,cy)}.get(side,(cx,cy))

def main(path):
    d = json.load(open(path, encoding="utf-8"))
    nodes = d["nodes"]; edges = d.get("edges", [])
    by_id = {n["id"]: n for n in nodes}
    groups = [n for n in nodes if n["type"] == "group"]
    cards  = [n for n in nodes if n["type"] != "group"]
    issues = []

    # 1. 스키마 — 타입당 콘텐츠 키 정확히 하나
    for n in nodes:
        want = CONTENT_KEY.get(n["type"], "?")
        have = [k for k in ("text","file","url") if k in n]
        if want is None:
            if have: issues.append(("SCHEMA", n["id"], "group인데 콘텐츠 키 %s 보유" % have))
        elif have != [want]:
            issues.append(("SCHEMA", n["id"], "type=%s 인데 키=%s (기대 [%s])" % (n["type"], have, want)))

    # 2. 20 스냅
    for n in nodes:
        bad = [(k, n[k]) for k in ("x","y","width","height") if n[k] % SNAP]
        if bad: issues.append(("SNAP", n["id"], "20의 배수 아님 %s" % bad))

    # 3. 카드끼리 겹침
    for a, b in itertools.combinations(cards, 2):
        if overlap(a, b): issues.append(("OVERLAP", "%s~%s" % (a["id"], b["id"]), "카드 겹침"))

    # 4. 그룹 포함 — 부분포함(라벨/클릭 오작동 원인) 적발
    for c in cards:
        part = [g for g in groups if overlap(c, g)]
        full = [g for g in part if inside(c, g)]
        if part and not full:
            issues.append(("GROUP", c["id"], "그룹 %s 에 걸쳐만 있음(부분포함)" % [g["id"] for g in part]))
        if len(full) > 1:
            # 중첩 그룹은 정상. 큰 것부터 정렬해 연쇄적으로 포함되면 통과.
            ch = sorted(full, key=lambda g: g["width"]*g["height"], reverse=True)
            if not all(inside(b, a) for a, b in zip(ch, ch[1:])):
                issues.append(("GROUP", c["id"], "그룹 %s 이 서로 중첩관계가 아닌데 함께 포함" % [g["id"] for g in full]))
        if not part:
            issues.append(("GROUP", c["id"], "어느 그룹에도 속하지 않음"))

    # 4b. 그룹끼리는 완전 중첩이거나 완전 분리여야 한다 (반쯤 걸치면 드래그가 예측 불가)
    for a, b in itertools.combinations(groups, 2):
        if overlap(a, b) and not (inside(a, b) or inside(b, a)):
            issues.append(("GROUP", "%s~%s" % (a["id"], b["id"]), "그룹끼리 부분 겹침"))

    # 5. 그룹 라벨 여백 — 라벨은 그룹 상단 바깥/경계에 그려진다. 상단 40px 안에 카드가 있으면 겹친다.
    for g in groups:
        for c in cards:
            if inside(c, g) and c["y"] - g["y"] < 40:
                issues.append(("LABEL", g["id"], "카드 %s 가 상단에서 %dpx — 라벨과 충돌" % (c["id"], c["y"]-g["y"])))

    # 6. 행·열 정렬 — 같은 x끼리 열, 같은 y끼리 행. 근접하나 불일치한 값 적발
    for axis in ("x","y"):
        vals = sorted({c[axis] for c in cards})
        for a, b in zip(vals, vals[1:]):
            if 0 < b - a <= 60:
                ids = [c["id"] for c in cards if c[axis] in (a,b)]
                issues.append(("ALIGN", axis, "%d 와 %d 가 %dpx 차 — 정렬 의도면 통일 %s" % (a,b,b-a,ids)))

    # 7. 엣지가 제3의 카드를 관통 (직선 근사)
    for e in edges:
        f, t = by_id.get(e["fromNode"]), by_id.get(e["toNode"])
        if not f or not t:
            issues.append(("EDGE", e.get("id","?"), "존재하지 않는 노드 참조")); continue
        p, q = anchor(f, e.get("fromSide")), anchor(t, e.get("toSide"))
        for c in cards:
            if c["id"] in (f["id"], t["id"]): continue
            if seg_rect_hit(p, q, c):
                issues.append(("CROSS", e.get("id","?"), "%s→%s 선이 %s 를 관통" % (f["id"], t["id"], c["id"])))

    # 8~11. kepano json-canvas SKILL.md 의 Validation Checklist 흡수 (스킬 벤더링은 기각, 항목만 가져옴)
    VALID_COLOR = lambda c: c in list("123456") or (isinstance(c, str) and c.startswith("#") and len(c) in (4, 7))
    ids = [n["id"] for n in nodes] + [e["id"] for e in edges if "id" in e]
    for i in sorted(set(ids)):
        if ids.count(i) > 1: issues.append(("ID", i, "id 중복 %d회" % ids.count(i)))
    for n in nodes:
        if n["type"] not in ("text", "file", "link", "group"):
            issues.append(("TYPE", n["id"], "알 수 없는 type=%r" % n["type"]))
        if "color" in n and not VALID_COLOR(n["color"]):
            issues.append(("COLOR", n["id"], "색상 %r — 프리셋 1~6 또는 hex 아님" % n["color"]))
    for e in edges:
        eid = e.get("id", "?")
        for k in ("fromSide", "toSide"):
            if k in e and e[k] not in ("top", "right", "bottom", "left"):
                issues.append(("SIDE", eid, "%s=%r" % (k, e[k])))
        for k in ("fromEnd", "toEnd"):
            if k in e and e[k] not in ("none", "arrow"):
                issues.append(("END", eid, "%s=%r" % (k, e[k])))
        if "color" in e and not VALID_COLOR(e["color"]):
            issues.append(("COLOR", eid, "엣지 색상 %r" % e["color"]))

    print("파일: %s" % os.path.basename(path))
    print("노드 %d (그룹 %d / 카드 %d) · 엣지 %d" % (len(nodes), len(groups), len(cards), len(edges)))
    if not issues:
        print("\nPASS — 검출 0건"); return 0
    print("\n검출 %d건" % len(issues))
    cur = None
    for kind, who, msg in sorted(issues, key=lambda i: i[0]):
        if kind != cur: print("\n[%s]" % kind); cur = kind
        print("  %-14s %s" % (who, msg))
    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
