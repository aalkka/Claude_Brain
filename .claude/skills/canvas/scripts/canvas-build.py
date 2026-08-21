# -*- coding: utf-8 -*-
"""canvas-build — 스펙(JSON) → Obsidian .canvas.

왜 있는가: 2026-08-22 세션에서 캔버스 1장을 만드는 데 든 도구호출 49건 중 32건(65%)이
**형식**이었다(카드 크기·간격·엣지 관통·라벨 폭·렌더 확인). 내용은 35%. 그 65%는 일회성
지식이라 여기 상수와 규칙으로 고정한다. 두 번째 캔버스부터는 내용만 쓰면 된다.

소유 경계 (하드규칙):
  기계 = 노드 집합 · 엣지 · 라벨 · 크기 · 그룹 박스
  사람 = x, y
  기존 파일에 같은 id의 노드가 있으면 **좌표를 절대 덮지 않는다**. 새 노드만 배치하고
  스펙에서 사라진 노드만 지운다. (08-22에 이 경계를 넘어 손좌표 y=1510을 덮은 전례가 있다.)

사용:
  py -3 canvas-build.py <spec.json> <out.canvas> [--regrid] [--window WxH]
  --regrid   좌표 보존을 끄고 전면 재배치. 사람이 옮긴 좌표가 사라지므로 승인 후에만.
  --window   창의 캔버스 영역 크기(기본 1560x1085). 밴드별 필요 축척·본문 px를 보고한다.

스펙 형식은 SKILL.md 참조.
"""
import json, io, os, sys, subprocess, argparse

# ── 실측 상수 (2026-08-22, 근거는 SKILL.md 표) ────────────────────────────
W          = 400   # 카드 폭. 열 안에서 폭이 다르면 넓은 쪽이 옆 열 차선을 막아 엣지가 관통한다.
H_TEXT     = 220   # kepano 권고 medium text 300-450 x 150-300 범위
H_FILE     = 440   # file preview 300-500 x 200-400 — 높이만 스크롤 위해 초과
GAP_COL    = 120   # 라벨이 이 틈에 그려진다. 라벨 폭보다 좁으면 카드 밑으로 들어간다.
GAP_ROW    = 80
PAD_GROUP  = 40    # 중첩 그룹 안쪽
PAD_BAND   = 60    # 바깥(밴드) 그룹 — 중첩 그룹 라벨과 겹치지 않게 더 크게
GAP_BAND   = 200   # 밴드끼리 세로 간격
SNAP       = 20
GLYPH_PX   = 14    # 한글 1자 ≈ 14px(축척 1.0 기준, 08-22 화면 실측 '정규화 MD' 108px/8자에서 역산)
FONT_PX    = 16    # Obsidian 본문 기본

def snap(v, m=SNAP): return int(round(v / m) * m)


def build(spec, existing=None, regrid=False):
    gap_col = spec.get("gap_col", GAP_COL)
    gap_row = spec.get("gap_row", GAP_ROW)
    nodes_in = spec["nodes"]
    keep = {}
    if existing and not regrid:
        keep = {n["id"]: (n["x"], n["y"]) for n in existing.get("nodes", [])
                if n.get("type") != "group"}

    # ── 1. 크기 확정 ──────────────────────────────────────────────────
    for n in nodes_in:
        n["_type"] = "file" if "file" in n else "text"
        n["_w"] = W
        n["_h"] = n.get("height") or (H_FILE if n["_type"] == "file" else H_TEXT)

    # ── 2. 열 x ───────────────────────────────────────────────────────
    cols = sorted({n["col"] for n in nodes_in})
    colx, x = {}, 0
    for c in cols:
        colx[c] = snap(x); x = snap(x) + W + gap_col

    # ── 3. 행 y — **열마다 독립으로 쌓는다**. 열은 서로 다른 개수·높이의 카드를 담고,
    #    열 사이의 뜻은 행이 아니라 엣지가 나른다. 열을 가로로 맞추고 싶으면 노드에 "y"를 직접 준다.
    bands = [b["id"] for b in spec.get("bands", [])] or [None]
    band_y, cursor, rowy = {}, 0, {}
    # 밴드에 속하지 않는 카드(참조용 등)는 밴드 흐름을 밀지 않는다. y=0에서 독립으로 쌓는다.
    if any(n.get("band") is None for n in nodes_in): bands = [None] + bands
    for b in bands:
        mine = [n for n in nodes_in if n.get("band") == b]
        if not mine:
            band_y[b] = cursor; continue
        band_y[b] = cursor
        bottom = 0
        for c in sorted({n["col"] for n in mine}):
            y = 0
            for n in sorted((n for n in mine if n["col"] == c and "y" not in n),
                            key=lambda n: n["row"]):
                rowy[(b, c, n["row"])] = y
                y += n["_h"] + gap_row
            bottom = max(bottom, y - gap_row)
        for n in mine:
            if "y" in n: bottom = max(bottom, n["y"] + n["_h"])
        if b is not None: cursor += bottom + PAD_BAND * 2 + GAP_BAND

    # ── 4. 좌표 배정. 이미 있던 노드는 사람 좌표를 되쓴다.
    out_nodes = []
    for n in nodes_in:
        b = n.get("band")
        y = (n["y"] if "y" in n else rowy[(b, n["col"], n["row"])]) + band_y.get(b, 0)
        node = {"id": n["id"], "type": n["_type"],
                "x": colx[n["col"]], "y": snap(y), "width": n["_w"], "height": n["_h"]}
        if n["id"] in keep:
            node["x"], node["y"] = keep[n["id"]]          # ← 소유 경계
        node["file" if n["_type"] == "file" else "text"] = n.get("file") or n.get("text", "")
        if "color" in n: node["color"] = n["color"]
        out_nodes.append(node)

    by = {n["id"]: n for n in out_nodes}

    # ── 5. 그룹 박스 — 멤버에서 계산. 중첩 그룹을 먼저, 밴드를 나중에.
    groups = []
    def box(ids, pad):
        ms = [by[i] for i in ids]
        x1 = snap(min(m["x"] for m in ms) - pad); y1 = snap(min(m["y"] for m in ms) - pad)
        return dict(x=x1, y=y1,
                    width=snap(max(m["x"] + m["width"] for m in ms) + pad) - x1,
                    height=snap(max(m["y"] + m["height"] for m in ms) + pad) - y1)
    for g in spec.get("groups", []):
        gg = {"id": g["id"], "type": "group", "label": g["label"], **box(g["members"], PAD_GROUP)}
        if "color" in g: gg["color"] = g["color"]
        by[g["id"]] = gg; groups.append(gg)
    for b in spec.get("bands", []):
        ids = [n["id"] for n in nodes_in if n.get("band") == b["id"]]
        ids += [g["id"] for g in spec.get("groups", [])
                if all(m in ids for m in g["members"])]
        if not ids: continue
        gg = {"id": b["id"], "type": "group", "label": b["label"], **box(ids, PAD_BAND)}
        if "color" in b: gg["color"] = b["color"]
        by[b["id"]] = gg; groups.insert(0, gg)      # 밴드가 먼저 그려져야 위에 안 덮인다

    # ── 6. 엣지 — 같은 열이면 세로(top/bottom), 다른 열이면 좌우.
    edges = []
    for i, e in enumerate(spec.get("edges", [])):
        f, t = by[e["from"]], by[e["to"]]
        if f["x"] == t["x"]:
            fs, ts = ("bottom", "top") if f["y"] < t["y"] else ("top", "bottom")
        else:
            fs, ts = ("right", "left") if f["x"] < t["x"] else ("left", "right")
        ed = {"id": e.get("id", "e%02d" % i), "fromNode": e["from"], "fromSide": e.get("fromSide", fs),
              "toNode": e["to"], "toSide": e.get("toSide", ts)}
        if e.get("label"): ed["label"] = e["label"]
        if "color" in e: ed["color"] = e["color"]
        edges.append(ed)

    return {"nodes": groups + out_nodes, "edges": edges}, colx, gap_col


def dump(d):
    """Obsidian 저장형식 = 노드 1줄. 예쁜 들여쓰기(283줄)는 카드 하나만 옮겨도 전량 churn."""
    o = ["{", '\t"nodes":[']
    o += ["\t\t" + json.dumps(n, ensure_ascii=False, separators=(",", ":")) + "," for n in d["nodes"]]
    if d["nodes"]: o[-1] = o[-1][:-1]
    o += ["\t],", '\t"edges":[']
    o += ["\t\t" + json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "," for e in d["edges"]]
    if d["edges"]: o[-1] = o[-1][:-1]
    o += ["\t]", "}"]
    return "\n".join(o) + "\n"


def report(d, gap_col, win):
    """라벨 폭 · 필요 축척 — 형식 실패의 두 상습 원인."""
    warn = []
    for e in d["edges"]:
        lb = e.get("label", "")
        if not lb: continue
        f = next(n for n in d["nodes"] if n["id"] == e["fromNode"])
        t = next(n for n in d["nodes"] if n["id"] == e["toNode"])
        if f["x"] == t["x"]: continue                    # 세로 엣지는 가로 제약 없음
        lane = abs(t["x"] - f["x"]) - W                  # 두 카드 사이 실제 빈 폭
        need = len(lb) * GLYPH_PX
        if need > lane:
            warn.append("라벨 %r %dpx > 틈 %dpx — 카드 밑으로 들어간다" % (lb, need, lane))
    print("\n[라벨 폭] " + ("이상 없음" if not warn else ""))
    for w in warn: print("  ⚠ " + w)

    ww, wh = win
    print("\n[필요 축척]  창 %dx%d 기준" % (ww, wh))
    for g in [n for n in d["nodes"] if n["type"] == "group"]:
        s = min(ww / g["width"], wh / g["height"])
        lim = "가로" if ww / g["width"] < wh / g["height"] else "세로"
        print("  %-12s %4dx%-4d  축척 %.2f (%s 결정) → 본문 %.1fpx%s"
              % (g["id"], g["width"], g["height"], s, lim, FONT_PX * s,
                 "" if FONT_PX * s >= 12 else "   ⚠ 12px 미만 = 안 읽힘"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("out")
    ap.add_argument("--regrid", action="store_true", help="사람 좌표 무시하고 전면 재배치(승인 필요)")
    ap.add_argument("--window", default="1560x1085")
    a = ap.parse_args()

    spec = json.load(io.open(a.spec, encoding="utf-8"))
    existing = None
    if os.path.exists(a.out) and not a.regrid:
        try: existing = json.load(io.open(a.out, encoding="utf-8"))
        except Exception: pass

    d, colx, gap_col = build(spec, existing, a.regrid)
    io.open(a.out, "w", encoding="utf-8", newline="\n").write(dump(d))

    kept = sum(1 for n in d["nodes"] if n["type"] != "group") if existing else 0
    print("%s — 노드 %d(그룹 %d) · 엣지 %d%s"
          % (os.path.basename(a.out), len(d["nodes"]),
             sum(1 for n in d["nodes"] if n["type"] == "group"), len(d["edges"]),
             "  · 기존 좌표 보존" if existing else "  · 신규"))
    ww, wh = (int(v) for v in a.window.lower().split("x"))
    report(d, gap_col, (ww, wh))

    chk = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canvas-check.py")
    print("\n[검사]"); sys.stdout.flush()      # 자식 출력이 앞질러 나오지 않게
    subprocess.call([sys.executable, chk, a.out])


if __name__ == "__main__":
    main()
