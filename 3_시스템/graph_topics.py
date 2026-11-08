# -*- coding: utf-8 -*-
"""**graph_topics** — 그래프뷰를 주제별로 보게 한다: 색 묶음(`.obsidian/graph.json` 의 `colorGroups`)과 필터 노트 구역을 폴더에서 만든다.

  py -3 3_시스템/graph_topics.py            미리 보기(아무것도 안 쓴다)
  py -3 3_시스템/graph_topics.py --write    colorGroups · 색표 · 필터 노트 구역을 쓴다
  --vault <볼트>   다른 볼트(시험 사본)의 폴더·graph.json·노트를 다룬다(역할표·과목표는 이 볼트 것)
  --table <파일>   색표 자리를 바꾼다(시험용)

만드는 것
- 주제 = 지식·작업·수집(+`_색인`) 층의 `<영역>/<주제>` 폴더 이름의 합집합(roles.json `topic_roots`). 파일이 하나도 없는 빈 폴더는 뺀다.
- 색 묶음 = 주제마다 3줄 — 지식(진함) · 작업(중간) · 수집(옅음, `_색인` 포함). 주제마다 색상(hue) 하나이고 층은 상대 휘도만 다르다.
  거기에 `_lms` 색인 노트를 과목별로 칠하는 줄(`lms/courses.json`)과 기록 노트의 `주제:` 속성 줄이 붙는다.
- `graph.json` 은 `colorGroups` 만 바꾼다(다른 칸·`search` 는 그대로). 이 대본 꼴(`path:"<층>/…`)이 아닌 남의 줄은 맨 앞에 그대로 둔다.
- 색표 `3_시스템/graph_topics.json` = 주제 이름 → hue·층별 색. 이미 있는 주제는 다시 돌려도 안 바뀐다(손으로 고쳐도 된다).
  새 주제는 이미 쓴 색과 가장 먼 hue 를 받는다(큰 주제부터 정하므로 큰 주제끼리 멀다). 눌린 노드 색(보라) 근처 hue 는 피한다.
- 필터 노트 `그래프뷰-주제별-필터` 의 `<!-- graph_topics:begin -->` ~ `<!-- graph_topics:end -->` 사이만 다시 쓴다.

색: 밝은 테마(배경 #fff)와 어두운 테마(배경 #1c1c1c) 양쪽에서 보이도록 층마다 상대 휘도를 같게 맞췄다(대비 2.5 이상).
적용(격리 옵시디언 1.15 실측, 2026-11-05): 열려 있는 그래프 보기는 밖에서 바뀐 graph.json 을 읽지 않는다 → 그래프 탭을 닫았다
다시 열면(또는 앱을 다시 켜면) 읽힌다. 열린 채로 그래프 설정을 하나라도 바꾸면 낡은 메모리 값이 파일을 덮어 색 묶음이 사라진다
(그땐 이 대본을 다시 돌린다). 정상 종료는 덮지 않는다.
"""
import argparse
import json
import math
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import roles  # noqa: E402

TABLE = os.path.join(HERE, "graph_topics.json")
COURSES = os.path.join(HERE, "lms", "courses.json")
NOTE_NAME = "그래프뷰-주제별-필터"
BEGIN, END = "<!-- graph_topics:begin -->", "<!-- graph_topics:end -->"
# (층, 목표 상대 휘도 Y, 목표 채도 C[OKLCH]) — 지식 진함 · 작업 중간 · 수집 옅음
TIERS = (("지식", 0.165, 0.20), ("작업", 0.25, 0.165), ("수집", 0.35, 0.12))
BG_LIGHT, BG_DARK = 1.0, 0.0116  # 그래프 배경의 상대 휘도: 밝은 #ffffff · 어두운 #1c1c1c (옵시디언 1.15 실측)
FOCUS_RGB = 0x8A5CF5             # 눌린·가리킨 노드 색 hsl(258 88% 66%)
SEED_HUE = 25.0                  # 가장 큰 주제가 받는 hue
DESC = ("그래프뷰 색 묶음의 색표 — graph_topics.py 가 읽고 쓴다. 주제 이름 → hue(OKLCH 도)·층별 색. "
        "이미 있는 주제는 다시 돌려도 안 바뀐다. 색을 바꾸려면 층별 색을 손으로 고치거나 주제 줄을 지우면 다음 실행에서 새로 받는다.")


# ───────────────────────── 색 ─────────────────────────
def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _oklch_lin(L, C, h):
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_, m_, s_ = L + 0.3963377774 * a + 0.2158037573 * b, L - 0.1055613458 * a - 0.0638541728 * b, L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def _in_gamut(rgb):
    return all(-1e-6 <= x <= 1 + 1e-6 for x in rgb)


def _max_chroma(L, h):
    lo, hi = 0.0, 0.4
    for _ in range(24):
        mid = (lo + hi) / 2
        if _in_gamut(_oklch_lin(L, mid, h)):
            lo = mid
        else:
            hi = mid
    return lo


def _lum(rgb_lin):
    r, g, b = (min(1.0, max(0.0, x)) for x in rgb_lin)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def tier_color(hue, y_target, c_target):
    """상대 휘도가 y_target 이 되는 L 을 찾고, 채도는 c_target 까지(색역 안에서)."""
    lo, hi = 0.05, 0.99
    for _ in range(40):
        L = (lo + hi) / 2
        C = min(c_target, _max_chroma(L, hue))
        if _lum(_oklch_lin(L, C, hue)) < y_target:
            lo = L
        else:
            hi = L
    rgb = _oklch_lin(L, min(c_target, _max_chroma(L, hue)), hue)
    return "#%02x%02x%02x" % tuple(round(255 * _gam(x)) for x in rgb)


def tier_colors(hue):
    return {name: tier_color(hue, y, c) for name, y, c in TIERS}


def hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rel_lum(hexc):
    r, g, b = (_lin(v / 255) for v in hex_rgb(hexc))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(y1, y2):
    hi, lo = max(y1, y2), min(y1, y2)
    return (hi + 0.05) / (lo + 0.05)


def oklab(hexc):
    r, g, b = (_lin(v / 255) for v in hex_rgb(hexc))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklch(hexc):
    L, a, b = oklab(hexc)
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def delta_e(c1, c2):
    return math.dist(oklab(c1), oklab(c2))


FOCUS_HUE = oklch("#%06x" % FOCUS_RGB)[2]


def circ(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


_mid_cache = {}


def mid_color(hue):
    k = round(hue)
    if k not in _mid_cache:
        _mid_cache[k] = tier_colors(float(k))["작업"]
    return _mid_cache[k]


def pick_hue(used_mid):
    """이미 쓴 중간색들과 색 거리(ΔE_OK)가 가장 먼 hue(1도 단위). 처음이면 SEED_HUE."""
    if not used_mid:
        return SEED_HUE
    best, best_h = -1.0, SEED_HUE
    for h in range(360):
        if circ(h, FOCUS_HUE) < 15:
            continue
        c = mid_color(h)
        d = min(delta_e(c, u) for u in used_mid)
        if d > best + 1e-9:
            best, best_h = d, float(h)
    return best_h


# ───────────────────────── 폴더 → 주제 ─────────────────────────
def _layers():
    r = roles.config()["roles"]
    return {"지식": r["knowledge"], "작업": r["work"], "수집": r["sources"]}, r["source_index"]


def _has_file(d):
    for _dp, _dn, fns in os.walk(d):
        if fns:
            return True
    return False


def _topic_dirs(V, area, name):
    L, idx = _layers()
    rels = [f"{L['지식']}/{area}/{name}", f"{L['작업']}/{area}/{name}", f"{L['수집']}/{area}/{name}", f"{idx}/{area}/{name}"]
    return [os.path.join(V, *r.split("/")) for r in rels]


def discover(V):
    """→ (영역 목록, [(영역, 주제)], {주제: md 수})"""
    L, idx = _layers()
    roots = set(L.values())
    areas = []
    for root in roles.config()["topic_roots"]:
        p = root.split("/")
        if len(p) == 2 and p[0] in roots and p[1] not in areas:
            areas.append(p[1])
    topics, counts = [], {}
    for a in areas:
        names = set()
        for base in [f"{L[t]}/{a}" for t in L] + [f"{idx}/{a}"]:
            d = os.path.join(V, *base.split("/"))
            if os.path.isdir(d):
                for n in os.listdir(d):
                    q = os.path.join(d, n)
                    if os.path.isdir(q) and not n.startswith((".", "_")) and _has_file(q):
                        names.add(n)
        for n in sorted(names):
            topics.append((a, n))
            md = 0
            for d in _topic_dirs(V, a, n):
                for _dp, _dn, fns in os.walk(d):
                    md += sum(1 for f in fns if f.lower().endswith(".md"))
            counts[n] = counts.get(n, 0) + md
    return areas, topics, counts


# ───────────────────────── 색표 ─────────────────────────
def load_table(path):
    try:
        with open(path, encoding="utf-8") as f:
            t = json.load(f)
    except FileNotFoundError:
        t = {}
    t["_설명"] = DESC
    t.setdefault("주제", {})
    return t


def ensure_colors(table, topics, counts):
    """색표에 없는 주제만 새 hue 를 준다(큰 주제부터). → 새로 정한 주제 이름들"""
    cur = table["주제"]
    names = sorted({n for _a, n in topics}, key=lambda n: (-counts.get(n, 0), n))
    used = [cur[n]["작업"] for n in cur if isinstance(cur[n], dict) and "작업" in cur[n]]
    new = []
    for n in names:
        e = cur.get(n)
        if isinstance(e, dict) and all(t in e for t, _y, _c in TIERS):
            continue
        if isinstance(e, dict) and "hue" in e:  # 일부 칸만 빠짐 — hue 는 지키고 칸만 채운다
            for t, c in tier_colors(float(e["hue"])).items():
                e.setdefault(t, c)
        else:
            h = pick_hue(used)
            e = {"hue": h, **tier_colors(h)}
            cur[n] = e
        used.append(e["작업"])
        new.append(n)
    return new


# ───────────────────────── 색 묶음 ─────────────────────────
def _find_note(V, name):
    root = os.path.join(V, *roles.path("knowledge").split("/"))
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        if name + ".md" in fns:
            return os.path.join(dp, name + ".md")
    return None


def _session_topics(V):
    """기록 노트 프론트매터의 `주제:` 값(원문) → 정식 주제 이름. 값이 정식 이름·별칭이 아니면 건너뛴다."""
    out, skipped = {}, set()
    d = os.path.join(V, *roles.path("sessions").split("/"))
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not fn.lower().endswith(".md"):
            continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8", errors="replace") as f:
                head = f.read(4000)
        except OSError:
            continue
        m = re.match(r"\A---\r?\n(.*?)\r?\n---", head, re.S)
        mm = re.search(r"^주제:[ \t]*(.+)$", m.group(1), re.M) if m else None
        if not mm:
            continue
        v = mm.group(1).strip()
        vals = [x.strip().strip("\"'") for x in v.strip("[]").split(",")] if v.startswith("[") else [v.strip("\"'")]
        for x in vals:
            if not x:
                continue
            c = roles.canon(x)
            if c:
                out[x] = c
            else:
                skipped.add(x)
    return out, skipped


def _lms_courses():
    try:
        with open(COURSES, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: str(v).split("/")[-1] for k, v in raw.items() if not k.startswith("_") and isinstance(v, str)}


def _pq(path):
    return 'path:"%s"' % path


def _prop(v):
    return v if re.fullmatch(r"[0-9A-Za-z_가-힣\-]+", v) else '"%s"' % v


def build_groups(V, topics, table):
    L, idx = _layers()
    sess = roles.path("sessions")
    g, warn = [], []

    def add(query, hexc):
        g.append({"query": query, "color": {"a": 1, "rgb": int(hexc.lstrip("#"), 16)}})

    for area, name in topics:
        e = table["주제"][name]
        add(_pq(f"{L['지식']}/{area}/{name}/"), e["지식"])
        add(_pq(f"{L['작업']}/{area}/{name}/"), e["작업"])
        add(_pq(f"{L['수집']}/{area}/{name}/") + " OR " + _pq(f"{idx}/{area}/{name}/"), e["수집"])
    known = {n for _a, n in topics}
    n_topic = len(g)
    sv, skipped = _session_topics(V)
    for raw in sorted(sv):
        if sv[raw] in known:
            add(_pq(sess + "/") + " [주제:%s]" % _prop(raw), table["주제"][sv[raw]]["지식"])
    n_sess = len(g) - n_topic
    if skipped:
        warn.append("기록의 `주제:` 값 중 주제 등록부에 없어 건너뜀: " + ", ".join(sorted(skipped)))
    for cid, name in sorted(_lms_courses().items()):
        if name in known:
            add(_pq(f"{idx}/_lms/lms-board-{cid}-"), table["주제"][name]["수집"])
        else:
            warn.append(f"courses.json 의 {cid}→{name} 은 주제 폴더가 없어 건너뜀")
    n_lms = len(g) - n_topic - n_sess
    return g, (n_topic, n_sess, n_lms), warn


def _ours(query):
    L, _idx = _layers()
    return re.match(r'^path:"(?:%s)/' % "|".join(re.escape(x) for x in L.values()), query) is not None


# ───────────────────────── 쓰기 ─────────────────────────
def _write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def _dumps(obj, nl):
    return json.dumps(obj, ensure_ascii=False, indent=2) + ("\n" if nl else "")


def note_region(areas, topics):
    out = [BEGIN]
    for a in areas:
        ts = [n for aa, n in topics if aa == a]
        if not ts:
            continue
        out.append("## " + a)
        for n in ts:
            out += ["### " + n, "```", f'path:"{a}/{n}/"', "```", ""]
    out.append(END)
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="그래프뷰 주제별 색 묶음·필터 노트 구역을 폴더에서 만든다(미리 보기가 기본).")
    ap.add_argument("--write", action="store_true", help="graph.json colorGroups · 색표 · 필터 노트 구역을 쓴다")
    ap.add_argument("--vault", default=VAULT, help="다룰 볼트 뿌리(기본 = 이 볼트)")
    ap.add_argument("--table", default=TABLE, help="색표 파일(기본 3_시스템/graph_topics.json)")
    a = ap.parse_args(argv)
    V = os.path.abspath(a.vault)
    if a.write and V != os.path.abspath(VAULT) and os.path.abspath(a.table) == os.path.abspath(TABLE):
        print("다른 볼트에 쓸 때는 --table 도 따로 지정한다(이 볼트의 색표를 건드리지 않게).")
        return 2
    gpath = os.path.join(V, ".obsidian", "graph.json")
    if not os.path.isfile(gpath):
        print("graph.json 이 없다: " + gpath + " (옵시디언에서 그래프뷰를 한 번 열면 생긴다)")
        return 2

    areas, topics, counts = discover(V)
    table = load_table(a.table)
    had = {n for _a, n in topics if n in table["주제"] and all(t in table["주제"][n] for t, _y, _c in TIERS)}
    new = ensure_colors(table, topics, counts)
    groups, (n_topic, n_sess, n_lms), warn = build_groups(V, topics, table)

    with open(gpath, encoding="utf-8") as f:
        raw = f.read()
    graph = json.loads(raw)
    nl = raw.endswith("\n")
    same_format = _dumps(graph, nl) == raw
    old = graph.get("colorGroups", [])
    foreign = [x for x in old if not _ours(x.get("query", ""))]
    final = foreign + groups
    out_graph = dict(graph)
    out_graph["colorGroups"] = final  # 키가 이미 있으면 자리 그대로, 없으면 끝에
    graph_text = _dumps(out_graph, nl)

    note_path = _find_note(V, NOTE_NAME)
    note_text = note_new = None
    if note_path:
        with open(note_path, encoding="utf-8") as f:
            note_text = f.read()
        if BEGIN in note_text and END in note_text:
            region = note_region(areas, topics)
            note_new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _m: region, note_text, count=1, flags=re.S)

    # ── 보고
    print("볼트: " + V)
    print("주제 %d (%s) · 주제 안 md %d개" % (len(topics), " · ".join("%s %d" % (x, sum(1 for aa, _n in topics if aa == x)) for x in areas), sum(counts.values())))
    print("색표: " + a.table + " — 이미 있음 %d · 새로 정함 %d%s" % (len(had), len(new), (" (" + ", ".join(new) + ")") if new and len(new) <= 8 else ""))
    print("%-4s %-22s %5s %6s  %-8s %-8s %-8s" % ("영역", "주제", "md", "hue", "지식", "작업", "수집"))
    for area, name in topics:
        e = table["주제"][name]
        print("%-4s %-22s %5d %6.1f  %-8s %-8s %-8s%s" % (area, name, counts.get(name, 0), e["hue"], e["지식"], e["작업"], e["수집"], "  ← 새" if name in new else ""))
    used = [table["주제"][n]["작업"] for _a, n in topics]
    if len(used) > 1:
        dmin = min((delta_e(used[i], used[j]), topics[i][1], topics[j][1]) for i in range(len(used)) for j in range(i + 1, len(used)))
        print("가장 가까운 두 주제의 색 거리(ΔE_OK, 중간색): %.3f — %s · %s" % dmin)
    for t, _y, _c in TIERS:
        ys = [rel_lum(table["주제"][n][t]) for _a, n in topics]
        print("대비 최저(%s): 밝은 배경 %.2f:1 · 어두운 배경 %.2f:1" % (t, min(contrast(y, BG_LIGHT) for y in ys), min(contrast(y, BG_DARK) for y in ys)))
    print("묶음: 총 %d줄 = 주제 %d + 기록 속성 %d + _lms 과목 %d · 앞에 둔 남의 줄 %d" % (len(final), n_topic, n_sess, n_lms, len(foreign)))
    print("graph.json: colorGroups %d줄 → %d줄 · 다른 칸·search(%r) 그대로 · 쓰기 꼴 %s" % (len(old), len(final), graph.get("search", ""), "동일" if same_format else "달라짐(JSON 은 유효)"))
    print("필터 노트: " + (os.path.relpath(note_path, V) if note_path else "없음 — 구역 건너뜀") + ((" · 구역 " + ("바뀜" if note_new != note_text else "그대로")) if note_new is not None else (" · 표시 없음 — 건너뜀" if note_path else "")))
    for w in warn:
        print("주의: " + w)

    if not a.write:
        print("미리 보기 — 아무것도 쓰지 않았다. 적용: --write")
        return 0

    wrote = []
    table_text = json.dumps(table, ensure_ascii=False, indent=1) + "\n"
    try:
        with open(a.table, encoding="utf-8") as f:
            table_old = f.read()
    except FileNotFoundError:
        table_old = None
    try:
        if table_text != table_old:
            _write_atomic(a.table, table_text)
            wrote.append("색표")
        if graph_text != raw:
            _write_atomic(gpath, graph_text)
            wrote.append("graph.json")
        if note_new is not None and note_new != note_text:
            _write_atomic(note_path, note_new)
            wrote.append("필터 노트")
    except OSError as e:
        print("쓰기 실패(%s) — 쓴 것: %s" % (e, ", ".join(wrote) or "없음"))
        return 1
    print("썼다: " + (", ".join(wrote) if wrote else "바뀐 것 없음"))
    if "graph.json" in wrote:
        print("확인: 그래프 탭을 닫았다 다시 열면 읽힌다(앱을 다시 켜도 된다). 열어 둔 그래프에서 설정을 바꾸면 낡은 메모리 값이 파일을 덮으니 그땐 다시 돌린다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
