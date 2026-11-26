"""필기(.note · .sdocx) → 쪽 조각 PNG(오프라인) · 필요할 때만 손글씨 전사(조각 해시 캐시).

Claude 는 .note(JSON 줄 · 획 = base64 차이값)와 .sdocx(삼성노트 zip · 이진)를 Read 로 읽지 못한다 → 쪽을 그림으로 그려 읽힌다.
잰 값(11-21 · 견본 5개 · Claude 전사 글자 85~100% · 오프라인 OCR·획 인식기 0~15%).

사용:
  py -3 3_시스템/inkrender.py <파일> [--page N] [--out 폴더] [--width 1240]
      → 쪽 조각 PNG 경로를 한 줄씩 낸다(세션이 그 PNG 를 Read 로 본다 · 오프라인 · 사용량 0). --out 이 없으면 임시 폴더.
  py -3 3_시스템/inkrender.py <파일> --read [--page N] [--cache 폴더]
      → 손글씨를 Claude(claude -p · 구독 · ingest_vision.transcribe)로 옮긴 글을 낸다. 사용량이 든다 = 누를 때만(자동 호출 없음).
        조각 해시가 같으면 캐시에서 읽는다(필기를 덧붙여도 바뀐 조각만 다시 읽음).
  py -3 3_시스템/inkrender.py <파일> --since [--mark] [--out 폴더]
      → 지난번 표식 뒤 새로 쓴 부분만 쪽마다 잘라 그림(+ 위 맥락 회색 · 그 사이 지운 획 옅은 빨강 · 설명 띠) 경로를 낸다.
        표식 = 3_시스템/_index/inkrender/seen/<노트 id>.json(원본은 안 고침). 처음이면 마지막에 쓴 쪽 전체.
        --mark = 지금 상태를 «본 것»으로 적는다(피드백을 준 뒤 · --since 와 함께 주면 그린 뒤 적음).
  py -3 3_시스템/inkrender.py <파일> --since --view 쪽[,y0,y1] [--json]
      → 표식과 무관하게 그 쪽(세로 범위 · 쪽 좌표)의 획 전부를 L번호와 함께 그림(곁창 «정리·옮겨 적기» 등 · 표식 안 바꿈).
  py -3 3_시스템/inkrender.py <파일> --screen 쪽[,y0,y1][;쪽,y0,y1…] [--start N] [--all] [--label 글] [--json] [--mark]
      → 탭이 지금 보여 주는 범위만(최소 보기 · 11-22) · y1 이 쪽 높이를 넘으면 다음 쪽으로 이어 그림 · 새 획 검정·본 획 회색
        (--all = 모두 검정) · 잘린 줄·위/아래 남은 획 수·화면 밖 새 획(new_off)을 JSON 에 · --mark = 그 범위만 «본 것»에 더함.
  py -3 3_시스템/inkrender.py <파일> --kind
      → 노트 종류 짐작 한 줄 JSON {kind: 풀이|강의 필기|그림|실험 기록|메모, why, bg, ref}(오프라인 · 곁창 칩용 · --since --json 에도 kind 칸).
  py -3 3_시스템/inkrender.py --selftest

조각: 세로로 긴 쪽(삼성 무한 쪽 · 공간 낸 쪽)은 획이 걸치지 않는 빈 줄에서 A4 비율 근처로 자른다. 빈 쪽·빈 조각은 내지 않는다.
.note 풀이 = brain-source src/ink/format.ts 와 같은 차례(쪽·획·del·mv·po·ph·pdel·rc) · 부분 지우개 구멍(hs)·PDF 바탕은 그리지 않는다
  (바탕 PDF 의 글은 그 PDF 색인에 이미 있음).
.sdocx 풀이 = brain-source 파서 한 벌을 Node 명령줄로 번들한 것(`3_시스템/ink/sdocx-dump.cjs` · brain-source 가지 inkread
  918f251 `build/tools/sdocx-dump.cjs` · 환경 변수 BRAIN_SDOCX_DUMP 로 바꿀 수 있음) — 파이썬 이식은 파서 두 벌 유지 손해라 안 함.
원본은 읽기만 한다.
"""
import hashlib, json, math, os, re, subprocess, sys, tempfile, time

from PIL import Image, ImageDraw, ImageFont

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER_VERSION = "inkrender 1"          # 그림 꼴이 바뀌면 올린다 → 조각 해시가 바뀌어 다시 읽는다
SDOCX_DUMP = os.environ.get("BRAIN_SDOCX_DUMP") or os.path.join(VAULT, "3_시스템", "ink", "sdocx-dump.cjs")
CACHE = os.path.join(VAULT, "3_시스템", "_index", "ingest-vision", "ink")
WIDTH = 1240
TAG = "_(손글씨 — Claude 가 쪽 그림에서 읽은 글 · 원본 글자가 아님)_"
_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ───────── .note 풀이 ─────────
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
B64I = {c: i for i, c in enumerate(B64)}
PEN_W = [1.1, 2.0, 3.6]                 # format.ts WIDTH
INK = ["#1f2024", "#d43c3c", "#3f5bd6", "#1f8a52", "#e6b400"]   # format.ts INK(정해 둔 5색)


def decode_pts(z):
    """format.ts decodePts 와 같은 풀이(base64url → varint zigzag 차이 → x/10, y/10, p/255)"""
    by = []
    for i in range(0, len(z), 4):
        c = [B64I.get(z[i + j], -1) if i + j < len(z) else -1 for j in range(4)]
        n = (c[0] << 18) | (c[1] << 12) | (max(0, c[2]) << 6) | max(0, c[3])
        by.append((n >> 16) & 255)
        if c[2] >= 0:
            by.append((n >> 8) & 255)
        if c[3] >= 0:
            by.append(n & 255)
    vals, i = [], 0
    while i < len(by):
        v, mul = 0, 1
        while True:
            b = by[i]; i += 1
            v += (b & 0x7F) * mul; mul *= 128
            if not (b & 0x80 and i < len(by)):
                break
        vals.append(-(v + 1) // 2 if v % 2 else v // 2)
    pts, x, y, p = [], 0, 0, 0
    for k in range(0, len(vals) - 2, 3):
        x += vals[k]; y += vals[k + 1]; p += vals[k + 2]
        pts.append((x / 10, y / 10, p / 255))
    return pts


def load_note(path, history=False):
    """→ ([(쪽 너비, 쪽 높이, [획{id, pts, hl, w, rgb}])], 타자 글 []). 쪽 = 보이는 차례.
    history=True → 지운 획도 남긴다(s["dead"] = True · --since 의 «지난번 뒤 지운 획») · 둘째 값 = 머리 줄(노트 id)."""
    head, pages, strokes = None, [], {}
    with open(path, encoding="utf-8") as f:
        for ln in f:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if not isinstance(r, dict):
                continue
            if head is None:
                head = r
                continue
            if isinstance(r.get("page"), str):
                if not any(p["page"] == r["page"] for p in pages):
                    pg = {"page": r["page"], "h": r.get("h") if isinstance(r.get("h"), (int, float)) else None,
                          "bg": r.get("bg") if isinstance(r.get("bg"), int) else None,
                          "ib": r.get("ib") if isinstance(r.get("ib"), int) else None, "ibf": r.get("ibf") if isinstance(r.get("ibf"), str) else None}
                    at = next((i for i, p in enumerate(pages) if p["page"] == r.get("after")), -1)
                    if at >= 0:
                        pages.insert(at + 1, pg)
                    else:
                        pages.append(pg)
            elif isinstance(r.get("s"), str):
                if r.get("t") == "img":
                    continue
                c = r.get("c", 0) if isinstance(r.get("c"), int) else 0
                strokes[r["s"]] = {"id": r["s"], "p": r.get("p"), "hl": r.get("t") == "hl", "dead": False,
                                   "w": r.get("pw") if isinstance(r.get("pw"), (int, float)) and r.get("pw") > 0 else PEN_W[min(2, max(0, int(r.get("w") or 0)))],
                                   "rgb": r.get("rgb") if isinstance(r.get("rgb"), str) else INK[c % len(INK)],
                                   "pts": decode_pts(r.get("z") or "")}
            elif isinstance(r.get("del"), list):
                for i in r["del"]:
                    if i in strokes:
                        strokes[i]["dead"] = True
            elif isinstance(r.get("mv"), list):
                dx, dy = r.get("dx") or 0, r.get("dy") or 0
                for i in r["mv"]:
                    s = strokes.get(i)
                    if s:
                        s["pts"] = [(x + dx, y + dy, p) for x, y, p in s["pts"]]
            elif isinstance(r.get("po"), list):
                by = {p["page"]: p for p in pages}
                hd = [by[i] for i in map(str, r["po"]) if i in by]
                pages = hd + [p for p in pages if p not in hd]
            elif isinstance(r.get("pdel"), str):
                pages = [p for p in pages if p["page"] != r["pdel"]]
            elif isinstance(r.get("ph"), str) and isinstance(r.get("h"), (int, float)):
                for p in pages:
                    if p["page"] == r["ph"]:
                        p["h"] = r["h"]
            elif isinstance(r.get("rc"), list):
                for i in r["rc"]:
                    s = strokes.get(i)
                    if s:
                        s["rgb"] = r["rgb"] if isinstance(r.get("rgb"), str) else INK[int(r.get("c") or 0) % len(INK)]
    W, H = (head or {}).get("size") or [595, 842]
    out = []
    canvas = (head or {}).get("layout") == "canvas"
    bgp = ((head or {}).get("bg") or {}).get("path") if isinstance((head or {}).get("bg"), dict) else None
    for p in pages:
        ss = [s for s in strokes.values() if s["p"] == p["page"] and s["pts"] and (history or not s["dead"])]
        h = p.get("h") or H
        live = [s for s in ss if not s["dead"]]
        if history:
            # 곁창·표식용 = 필기 화면(brain-source board.pageH)과 같은 쪽 크기 — 바탕 PDF·넣은 PDF 쪽 = 그 PDF 쪽 크기 ·
            # 무한 캔버스 = 마지막 획 아래로 쪽 높이의 0.6 · 그 밖 = 적힌 높이(획이 넘쳐도 안 늘림). 다르면 쪽을 넘는 보는 범위가 다음 쪽에서 어긋난다(11-23 tc_tab).
            w = W
            pdf = (bgp, p["bg"]) if p.get("bg") is not None and bgp else (p["ibf"], p["ib"]) if p.get("ibf") and p.get("ib") is not None else None
            sz = _pdf_size(*pdf) if pdf else None
            if sz:
                w, h = sz
            elif canvas and live:
                h = max(h, math.ceil(max(y for s in live for _, y, _ in s["pts"]) + H * 0.6))
            out.append((w, h, ss))
            continue
        if live:
            h = max(h, max(y for s in live for _, y, _ in s["pts"]) + 10)
        out.append((W, h, ss))
    return out, (head or {}) if history else []


_PDF_SIZES = {}


def _pdf_size(rel, i):
    """볼트 상대 PDF 의 i 쪽(0부터) 크기(pt) — 못 열면 None(그땐 노트 머리 크기)."""
    path = os.path.join(VAULT, rel) if not os.path.isabs(rel) else rel
    if path not in _PDF_SIZES:
        try:
            import pypdfium2 as pdfium
            d = pdfium.PdfDocument(path)
            _PDF_SIZES[path] = [tuple(d[k].get_size()) for k in range(len(d))]
            d.close()
        except Exception:
            _PDF_SIZES[path] = []
    sz = _PDF_SIZES[path]
    return sz[i] if 0 <= i < len(sz) else None


# ───────── .sdocx 풀이(Node 번들) ─────────
def load_sdocx(path):
    if not os.path.isfile(SDOCX_DUMP):
        raise RuntimeError(f".sdocx 풀이기 없음: {SDOCX_DUMP}")
    with tempfile.TemporaryDirectory(prefix="inkrender-") as td:
        js = os.path.join(td, "d.json")
        r = subprocess.run(["node", SDOCX_DUMP, path, js], capture_output=True, timeout=300, creationflags=_NOWIN)
        if r.returncode:
            raise RuntimeError(".sdocx 풀기 실패: " + r.stderr.decode("utf-8", "replace").strip()[-300:])
        with open(js, encoding="utf-8") as f:
            d = json.load(f)
    typed = [t for t in [d.get("title") or "", d.get("body") or ""] + [x["text"] for p in d["pages"] for x in p.get("texts", [])] if t.strip()]
    pages = []
    for p in d["pages"]:
        ss = [{"id": f"{p.get('id', len(pages))}:{i}", "hl": bool(s["hl"]), "w": max(0.6, s["size"] * 0.5), "argb": s["argb"],
               "pts": [tuple(q) for q in s["pts"]], "dead": False} for i, s in enumerate(p["strokes"]) if s["pts"]]
        pages.append((p["w"], p["h"], ss))
    return pages, typed


def load(path):
    """→ (쪽들, 타자 글 줄들)"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".note":
        return load_note(path)
    if ext == ".sdocx":
        return load_sdocx(path)
    raise ValueError("필기 형식 아님: " + path)


# ───────── 쪽 조각 ─────────
def cuts(h, w, ss):
    """세로 자를 자리 — A4 비율(w × 1.414) 근처에서 획이 걸치지 않는 y."""
    spans = sorted((min(q[1] for q in s["pts"]), max(q[1] for q in s["pts"])) for s in ss)
    covered = []
    for a, b in spans:
        if covered and a <= covered[-1][1] + 2:
            covered[-1][1] = max(covered[-1][1], b)
        else:
            covered.append([a, b])
    gaps = [(covered[i][1] + covered[i + 1][0]) / 2 for i in range(len(covered) - 1)]
    target, y0, res = w * 1.414, 0, []
    while h - y0 > target * 1.25:
        cand = [g for g in gaps if y0 + target * 0.6 < g < y0 + target * 1.25]
        y = min(cand, key=lambda g: abs(g - (y0 + target))) if cand else y0 + target
        res.append(y)
        y0 = y
    return [0] + res + [h]


def _color(s):
    if s.get("rgb"):
        c = s["rgb"].lstrip("#")
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    v = s.get("argb", 0xFF000000)
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255)


def tiles(pages):
    """→ [{page, part, w, top, bottom, strokes, key}] — key = 그림 판 + 조각 획 내용 해시(그리기 전에 셈 · 캐시 열쇠)."""
    out = []
    for pi, (W, H, ss) in enumerate(pages, 1):
        if not ss:
            continue
        ys = cuts(H, W, ss)
        part = 0
        for a, b in zip(ys, ys[1:]):
            sel = [s for s in ss if a <= min(q[1] for q in s["pts"]) < b]
            if not sel:
                continue
            part += 1
            h = hashlib.sha256(f"{RENDER_VERSION}|{W}|{round(b - a, 1)}".encode())
            for s in sel:
                h.update(json.dumps([s["hl"], round(s["w"], 2), _color(s), [(round(x, 1), round(y - a, 1)) for x, y, _ in s["pts"]]]).encode())
            out.append({"page": pi, "part": part, "w": W, "top": a, "bottom": b, "strokes": sel, "key": h.hexdigest()[:24]})
    return out


def draw(t, width=WIDTH):
    """조각 하나 → PIL 그림(흰 바탕 · 형광펜 반투명)."""
    k = width / t["w"]
    img = Image.new("RGB", (width, max(1, int((t["bottom"] - t["top"]) * k))), "white")
    dr = ImageDraw.Draw(img, "RGBA")
    for s in t["strokes"]:
        pts = [(x * k, (y - t["top"]) * k) for x, y, _ in s["pts"]]
        col = _color(s) + ((90,) if s["hl"] else (255,))
        lw = max(1, int(round(s["w"] * k * (3 if s["hl"] else 1))))
        if len(pts) == 1:
            x, y = pts[0]
            dr.ellipse([x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2], fill=col)
        else:
            dr.line(pts, fill=col, width=lw, joint="curve")
    return img


def render(path, outdir=None, page=None, width=WIDTH):
    """→ (조각들(+ png 경로), 타자 글). page = 쪽 번호(1부터 · 그 쪽 조각만)."""
    pages, typed = load(path)
    ts = [t for t in tiles(pages) if page is None or t["page"] == page]
    outdir = outdir or os.path.join(tempfile.gettempdir(), "inkrender", hashlib.sha256(os.path.abspath(path).encode()).hexdigest()[:12])
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    for t in ts:
        t["png"] = os.path.join(outdir, f"{stem}-{t['page']}.{t['part']}.png")
        draw(t, width).save(t["png"])
    return ts, typed


# ───────── 전사(누를 때만) ─────────
def cached(t, cache=CACHE):
    """조각의 전사 글(캐시) · 없으면 None — ingest.py 가 색인을 만들 때 Claude 를 부르지 않고 이것만 본다."""
    cp = os.path.join(cache, t["key"] + ".json")
    if not os.path.isfile(cp):
        return None
    try:
        with open(cp, encoding="utf-8") as f:
            return json.load(f)["text"]
    except (OSError, ValueError, KeyError):
        return None


def read(ts, cache=CACHE, transcribe=None):
    """조각들 → [(조각, 글)] · 캐시 적중이면 부르지 않는다. transcribe(PIL 그림) → (글, 사용량, 오류) — 없으면 ingest_vision."""
    if transcribe is None:
        import ingest_vision as V

        def transcribe(img):
            return V.transcribe(V.png(img, V.HW_SIDE), V.profile())
    os.makedirs(cache, exist_ok=True)
    out, stat = [], {"hit": 0, "calls": 0, "in": 0, "out": 0, "fail": 0}
    for t in ts:
        cp = os.path.join(cache, t["key"] + ".json")
        hit = cached(t, cache)
        if hit is not None:
            out.append((t, hit))
            stat["hit"] += 1
            continue
        img = Image.open(t["png"]).convert("RGB") if t.get("png") else draw(t)
        txt, use, err = transcribe(img)
        if err:
            stat["fail"] += 1
            out.append((t, None))
            continue
        with open(cp, "w", encoding="utf-8") as f:
            json.dump({"text": txt, "usage": use, "v": RENDER_VERSION}, f, ensure_ascii=False)
        stat["calls"] += 1
        stat["in"] += (use or {}).get("in", 0)
        stat["out"] += (use or {}).get("out", 0)
        out.append((t, txt))
    return out, stat


def as_markdown(read_out, typed=()):
    """전사 결과 → 색인 본문 md(쪽 조각마다 머리 + 표시 + 글)."""
    parts = ["## 타자 글\n\n" + "\n".join(typed) + "\n"] if typed else []
    for t, txt in read_out:
        parts.append(f"## 쪽 {t['page']}.{t['part']}\n\n{TAG}\n\n{(txt or '(읽기 실패 — 다음에 다시)').strip()}\n")
    return "\n".join(parts)


# ───────── 지난번 뒤 새로 쓴 부분(--since · R1 «봐줘»·R2 «피드백» 공용) ─────────
# 표식 = 마지막으로 본(피드백한) 때 남아 있던 획 이름들 — 곁 파일 3_시스템/_index/inkrender/seen/<노트 id>.json(원본 .note 는 안 고침).
# 노트 id(머리 줄 "id")로 열쇠를 삼아 이름을 바꾸거나 옮겨도 이어진다(없으면 볼트 상대 경로 해시). .sdocx 는 «쪽 id:차례» 를 이름으로.
SEEN = os.path.join(VAULT, "3_시스템", "_index", "inkrender", "seen")
PIECE_PX = 1.15e6                           # 화면 그림 한 장 넓이 상한(모델이 줄이지 않는 크기 · 넘으면 줄 틈에서 나눔)
CTX = 0.25                                  # 앞 맥락 = 새 부분 위로 쪽 높이(A4 비율)의 이만큼(회색)


A4_W = 595.0                            # 필기 화면(board)의 쪽 폭(pt) — .sdocx 도 이 단위로 그린다(brain-source sdocxedit · k = 595/쪽 폭)


def _pt(pages):
    """.sdocx 쪽(삼성 화면 px · 폭 1600 등) → 필기 화면 단위(pt · 폭 595). 곁창의 보는 범위(--screen·--view)와 줄 자리(lines)는
    탭 board 의 쪽 좌표라 같은 단위여야 한다(11-23: 삼성 px 그대로 써 보낸 범위·L 자리가 2.69배 어긋남)."""
    out = []
    for W, H, ss in pages:
        k = A4_W / (W or A4_W)
        out.append((A4_W, H * k, [{**s, "w": s["w"] * k, "pts": [(x * k, y * k, p) for x, y, p in s["pts"]]} for s in ss]))
    return out


def _load_hist(path):
    """곁창·표식용(쪽 좌표 = 필기 화면 단위 pt). 전사 조각(tiles·read)은 load() 그대로(조각 해시 캐시를 지킴)."""
    if os.path.splitext(path)[1].lower() == ".note":
        pages, head = load_note(path, history=True)
        return pages, head.get("id") if isinstance(head.get("id"), str) else None
    return _pt(load_sdocx(path)[0]), None


def mark_key(path, nid):
    if nid:
        return re.sub(r"[^0-9A-Za-z_-]", "_", nid)
    return "p-" + hashlib.sha256(os.path.relpath(os.path.abspath(path), VAULT).replace(os.sep, "/").encode()).hexdigest()[:16]


def mark(path, seen_dir=SEEN):
    """지금 남아 있는 획을 «본 것»으로 적는다(피드백을 준 뒤에 부름) → 표식 파일 경로."""
    pages, nid = _load_hist(path)
    ids = sorted(s["id"] for _, _, ss in pages for s in ss if not s.get("dead"))
    os.makedirs(seen_dir, exist_ok=True)
    mp = os.path.join(seen_dir, mark_key(path, nid) + ".json")
    tmp = mp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"path": os.path.relpath(os.path.abspath(path), VAULT).replace(os.sep, "/"), "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "n": len(ids), "ids": ids}, f, ensure_ascii=False)
    os.replace(tmp, mp)
    return mp


def since(path, outdir=None, seen_dir=SEEN, width=WIDTH, view=None):
    """지난 표식 뒤 새로 쓴 획만 쪽마다 잘라 그림(+ 위 맥락 회색 · 그 사이 지운 획 옅은 빨강 · 맨 위 설명 띠).
    표식이 없으면(처음) = 마지막에 쓴 쪽 전체. → (그림 [{page, png, new, erased, box}], 요약 dict). 원본은 읽기만.
    view = (쪽 번호 1부터, y0, y1 | None) → 표식과 무관하게 그 쪽(그 세로 범위)의 획 전부를 검정으로(곁창 «정리·옮겨 적기» 처럼 보이는 자리 전체가 필요할 때)."""
    pages, nid = _load_hist(path)
    mp = os.path.join(seen_dir, mark_key(path, nid) + ".json")
    seen = None
    if view:
        vp, vy0, vy1 = view
        live = lambda s: not s.get("dead")
        inv = lambda s: vy0 is None or (max(q[1] for q in s["pts"]) >= vy0 and min(q[1] for q in s["pts"]) <= vy1)
        new_of = lambda pi, s: pi == vp - 1 and live(s) and inv(s)
        gone_of = lambda pi, s: False
    elif os.path.isfile(mp):
        with open(mp, encoding="utf-8") as f:
            seen = set(json.load(f).get("ids") or [])
    if view:
        pass
    elif seen is None:                       # 처음 — 마지막 획이 있는 쪽 전체(쪽 차례 끝 쪽이 아니라 «마지막으로 쓴» 쪽)
        def when(pi, i, s):                 # 획 이름 = 기기-<Date.now 36진 8자><순번> → 쓴 시각 · 없으면 쪽·차례
            m = re.match(r"[^-:]+-([0-9a-z]{8})", s["id"])
            return (int(m.group(1), 36) if m else -1, pi, i)
        last = max(((pi, when(pi, i, s)) for pi, (_, _, ss) in enumerate(pages) for i, s in enumerate(ss) if not s.get("dead")),
                   key=lambda x: x[1], default=None)
        pick = {last[0]} if last else set()
        new_of = lambda pi, s: pi in pick and not s.get("dead")
        gone_of = lambda pi, s: False
    else:
        new_of = lambda pi, s: not s.get("dead") and s["id"] not in seen
        gone_of = lambda pi, s: s.get("dead") and s["id"] in seen
    if view:
        seen = None                          # 맥락 회색 칸 없이 그 범위만
    outdir = outdir or os.path.join(tempfile.gettempdir(), "inkrender", "since-" + mark_key(path, nid))
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    stamp = time.strftime("%H%M%S")
    out = []
    nums = _note_lines(pages)
    for pi, (W, H, ss) in enumerate(pages):
        new = [s for s in ss if new_of(pi, s)]
        gone = [s for s in ss if gone_of(pi, s)]
        if not new and not gone:
            continue
        focus = new or gone
        y0 = min(q[1] for s in focus for q in s["pts"]) - 8
        y1 = max(q[1] for s in focus for q in s["pts"]) + 8
        c0 = max(0, y0 - CTX * W * 1.414) if seen is not None else max(0, y0)
        cross = [min(q[1] for q in s["pts"]) for s in ss if not s.get("dead") and min(q[1] for q in s["pts"]) < c0 < max(q[1] for q in s["pts"])]
        c0 = max(0, min(cross + [c0]) - 4)   # 맥락 위 끝이 줄 한가운데를 자르지 않게 그 줄 위까지
        k = width / W
        img = Image.new("RGB", (width, max(1, int((y1 - c0) * k))), "white")
        dr = ImageDraw.Draw(img, "RGBA")
        newid = {s["id"] for s in new}
        inside = lambda s: max(q[1] for q in s["pts"]) >= c0 and min(q[1] for q in s["pts"]) <= y1
        for s in gone:
            if inside(s):
                _stroke(dr, s, k, c0, (230, 60, 60, 110))
        for s in ss:
            if s.get("dead") or not inside(s):
                continue
            old = s["id"] not in newid
            _stroke(dr, s, k, c0, (160, 160, 160, 255) if old else _color(s) + ((90,) if s["hl"] else (255,)))
        note = (f"보는 자리 전체({len(new)}획)" if view else f"검정 = 지난번 피드백 뒤 새로 쓴 획 {len(new)}개 · 회색 = 앞 맥락(이미 본 부분)" if seen is not None
                else f"처음 보는 필기 — 마지막에 쓴 쪽 전체({len(new)}획)") + (f" · 옅은 빨강 = 그 사이 지운 획 {len(gone)}개" if gone else "")
        # 줄 번호(L1…) — 답이 «L5» 로 짚으면 화면이 그 줄로 간다(lines = 쪽 좌표 y 범위) · 번호는 왼쪽 여백 칸에(필기를 안 가림)
        lines = [ln for ln in nums[pi] if ln["y1"] >= c0 and ln["y0"] <= y1]   # 노트 전체에 한 번 매긴 번호(화면·턴이 바뀌어도 같은 줄 = 같은 번호)
        img = _gutter(img, [(ln["n"], (ln["y0"] - c0) * k, (ln["y1"] - c0) * k) for ln in lines])
        img = _band(img, f"{pi + 1}쪽 · " + note + " · 왼쪽 L번호 = 줄")
        png = os.path.join(outdir, f"{stem}-{pi + 1}쪽-새부분-{stamp}.png")
        img.save(png)
        out.append({"page": pi + 1, "png": png, "new": len(new), "erased": len(gone), "box": [round(c0, 1), round(y1, 1)],
                    "lines": [{**ln, "y0": round(ln["y0"], 1), "y1": round(ln["y1"], 1)} for ln in lines]})
    return out, {"first": seen is None, "new": sum(o["new"] for o in out), "erased": sum(o["erased"] for o in out),
                 "pages": [o["page"] for o in out], "mark": mp}



# ───────── 지금 화면(--screen · 최소 보기 · 11-22) ─────────
# 첫 그림 = 탭이 지금 보여 주는 세로 범위만(쪽 좌표 · 잘린 줄은 잘린 채) · 그 안의 «지난번 뒤 새로 쓴 획» = 검정, 이미 본 획 = 회색.
# 더 보기(위·아래·쪽 N)도 이 함수로 그린다(start = 이어지는 L번호). 볼트 클로드의 맥락 층(고른 글만 본문 · 나머지는 자리만)과 같은 원칙.
def parse_segs(spec):
    """«5,300,900» · «5» · «4,1500,2100;5,0,200» → [(쪽, y0|None, y1|None)] — y1 이 쪽 높이를 넘으면 다음 쪽으로 이어진다(normalize 에서)."""
    out = []
    for part in spec.split(";"):
        v = [x for x in part.strip().split(",") if x != ""]
        if not v:
            continue
        out.append((int(v[0]), float(v[1]) if len(v) > 2 else None, float(v[2]) if len(v) > 2 else None))
    return out


def _norm_segs(segs, dims):
    """쪽 높이를 넘은 범위는 다음 쪽으로 넘긴다(쪽 사이 틈은 무시) · 없는 쪽·빈 범위는 뺀다."""
    out = []
    for p, y0, y1 in segs:
        if not 1 <= p <= len(dims):
            continue
        H = dims[p - 1][1]
        y0 = 0.0 if y0 is None else max(0.0, y0)
        y1 = H if y1 is None else y1
        while p <= len(dims) and y1 > y0:
            H = dims[p - 1][1]
            out.append((p, y0, min(y1, H)))
            if y1 <= H:
                break
            y1 -= H
            y0 = 0.0
            p += 1
    return out


def screen(path, segs, outdir=None, seen_dir=SEEN, width=WIDTH, start=1, split_new=True, label="지금 탭 화면"):
    """segs 범위만 그림 → (그림 [{page, png, new, erased, box, lines, cut_top, cut_bottom}], 요약 {dims, segs, new_off, first}).
    split_new = 지난 표식 뒤 새 획 검정 · 본 획 회색(표식이 없으면 모두 검정) · False = 모두 검정(정리·옮겨 적기)."""
    pages, nid = _load_hist(path)
    dims = [(W, H) for W, H, _ in pages]
    segs = _norm_segs(segs, dims)
    mp = os.path.join(seen_dir, mark_key(path, nid) + ".json")
    seen = None
    if split_new and os.path.isfile(mp):
        with open(mp, encoding="utf-8") as f:
            seen = set(json.load(f).get("ids") or [])
    span = lambda s: (min(q[1] for q in s["pts"]), max(q[1] for q in s["pts"]))
    hit = lambda s, a, b: s["pts"] and span(s)[1] >= a and span(s)[0] <= b
    outdir = outdir or os.path.join(tempfile.gettempdir(), "inkrender", "screen-" + mark_key(path, nid))
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    stamp = time.strftime("%H%M%S") + f"{int(time.time() * 1000) % 1000:03d}"
    # 긴 범위(쪽 전체 등)는 줄 틈에서 나눠 그림 여러 장으로 — 한 장이 1.15MP 를 넘으면 모델 쪽에서 줄여 어깨 글자(ℝ⁸)를 3 으로 잘못 읽음(11-22 잼)
    pieces = []
    for p, a, b in segs:
        W, H, ss = pages[p - 1]
        k = width / W
        cnt = math.ceil((width + 64) * (b - a) * k / PIECE_PX)
        if cnt <= 1:
            pieces.append((p, a, b))
            continue
        gaps = [(l1["y1"] + l2["y0"]) / 2 for l1, l2 in zip(*(lambda L: (L, L[1:]))(_lines([s for s in ss if not s.get("dead") and hit(s, a, b)])))]
        cuts_at, prev = [], a
        for i in range(1, cnt):
            want = a + (b - a) * i / cnt
            g = min((x for x in gaps if prev + 40 < x < b - 40), key=lambda x: abs(x - want), default=None)
            if g is not None and abs(g - want) < (b - a) / cnt / 2:
                cuts_at.append(g)
                prev = g
        edges = [a] + cuts_at + [b]
        pieces += [(p, edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
    out, n = [], start
    nums = _note_lines(pages)
    for p, a, b in pieces:
        W, H, ss = pages[p - 1]
        live = [s for s in ss if not s.get("dead") and hit(s, a, b)]
        gone = [s for s in ss if s.get("dead") and seen is not None and s["id"] in seen and hit(s, a, b)]
        if not live and not gone:
            continue
        new = [s for s in live if seen is None or s["id"] not in seen]
        k = width / W
        img = Image.new("RGB", (width, max(1, int((b - a) * k))), "white")
        dr = ImageDraw.Draw(img, "RGBA")
        for s in gone:
            _stroke(dr, s, k, a, (230, 60, 60, 110))
        newid = {s["id"] for s in new}
        for s in live:
            _stroke(dr, s, k, a, _color(s) + ((90,) if s["hl"] else (255,)) if s["id"] in newid else (160, 160, 160, 255))
        # 번호 = 노트 전체에 한 번 매긴 것(11-23: 화면·더 보기·턴마다 1부터 다시 매겨 앞 답의 L 이 다른 줄을 짚음)
        # 화면 끝에 걸친 줄은 잘린 채로 둔다(사람이 보는 그대로) — 번호는 보이는 만큼만
        lines = [{**ln, "y0": max(ln["y0"], a), "y1": min(ln["y1"], b)} for ln in nums[p - 1] if ln["y1"] >= a and ln["y0"] <= b]
        n = max([n] + [ln["n"] + 1 for ln in lines])
        img = _gutter(img, [(ln["n"], (ln["y0"] - a) * k, (ln["y1"] - a) * k) for ln in lines])
        cut_top = any(span(s)[0] < a - 2 for s in live)
        cut_bot = any(span(s)[1] > b + 2 for s in live)
        above = sum(1 for s in ss if not s.get("dead") and s["pts"] and span(s)[1] < a) + sum(1 for _, _, s2 in pages[:p - 1] for s in s2 if not s.get("dead"))
        below = sum(1 for s in ss if not s.get("dead") and s["pts"] and span(s)[0] > b) + sum(1 for _, _, s2 in pages[p:] for s in s2 if not s.get("dead"))
        tone = ("모두 검정(표식 없음 = 처음 봄)" if seen is None else f"검정 = 지난번 뒤 새로 쓴 획 {len(new)}개 · 회색 = 이미 본 획") if split_new else "보이는 획 전부"
        edge = " · ".join(x for x in (("위 끝에서 줄이 잘림" if cut_top else ""), ("아래 끝에서 줄이 잘림" if cut_bot else "")) if x)
        img = _band(img, f"{label} · {p}쪽 y {a:.0f}~{b:.0f}/{H:.0f} · {tone}" + (f" · 옅은 빨강 = 지운 획 {len(gone)}" if gone else "") + (f" · {edge}" if edge else ""))
        png = os.path.join(outdir, f"{stem}-{p}쪽-{int(a)}-{int(b)}-{stamp}.png")
        img.save(png)
        out.append({"page": p, "png": png, "new": len(new), "erased": len(gone), "box": [round(a, 1), round(b, 1)],
                    "cut_top": cut_top, "cut_bottom": cut_bot, "above": above, "below": below, "px": [img.width, img.height],
                    "lines": [{**ln, "y0": round(ln["y0"], 1), "y1": round(ln["y1"], 1)} for ln in lines]})
    inside = lambda pi, s: any(p == pi + 1 and hit(s, a, b) for p, a, b in segs)
    new_off = {}
    if seen is not None:
        for pi, (_, _, ss) in enumerate(pages):
            c = sum(1 for s in ss if not s.get("dead") and s["id"] not in seen and not inside(pi, s))
            if c:
                new_off[pi + 1] = c
    return out, {"dims": [[round(W, 1), round(H, 1)] for W, H in dims], "segs": [[p, round(a, 1), round(b, 1)] for p, a, b in segs],
                 "new_off": new_off, "first": seen is None, "next": n}


def mark_segs(path, segs, seen_dir=SEEN):
    """본 범위만 «본 것»에 더한다(화면·더 본 곳) — 화면 밖 새 획은 다음에 다시 새것으로 남는다."""
    pages, nid = _load_hist(path)
    segs = _norm_segs(segs, [(W, H) for W, H, _ in pages])
    mp = os.path.join(seen_dir, mark_key(path, nid) + ".json")
    old = set()
    if os.path.isfile(mp):
        with open(mp, encoding="utf-8") as f:
            old = set(json.load(f).get("ids") or [])
    ids = set()
    for pi, (_, _, ss) in enumerate(pages):
        for s in ss:
            inn = s["pts"] and any(p == pi + 1 and max(q[1] for q in s["pts"]) >= a and min(q[1] for q in s["pts"]) <= b for p, a, b in segs)
            if inn:
                if not s.get("dead"):
                    ids.add(s["id"])
            elif s["id"] in old:
                ids.add(s["id"])
    os.makedirs(seen_dir, exist_ok=True)
    tmp = mp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"path": os.path.relpath(os.path.abspath(path), VAULT).replace(os.sep, "/"), "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "n": len(ids), "ids": sorted(ids)}, f, ensure_ascii=False)
    os.replace(tmp, mp)
    return mp


# ───────── 노트 종류 짐작(오프라인 · 사용량 0) ─────────
# 곁창이 열리자마자 종류별 칩을 내려고 쓴다 — 모델이 첫 답 첫 줄 «〔종류: …〕» 로 바로잡는다(작업.md §3-1).
KINDS = ("풀이", "강의 필기", "그림", "실험 기록", "메모")
_NAME = [("풀이", r"과제|숙제|풀이|문제|연습|시험|퀴즈|중간|기말|hw\d*|homework|assignment|exercise|problem|quiz|exam|ps\d+"),
         ("실험 기록", r"실험|측정|lab\b|labs?\d|experiment"),
         ("강의 필기", r"강의|수업|lecture|chapter|ch\.?\s*\d|\(필기\)|정리|요약|summary")]


def _head_ops(path):
    """.note 머리(bg)와 옆 문제(ref · 마지막 것)."""
    bg = ref = None
    if os.path.splitext(path)[1].lower() != ".note":
        return bg, ref
    with open(path, encoding="utf-8") as f:
        for i, ln in enumerate(f):
            if i == 0 or '"ref"' in ln or '"bg"' in ln[:200]:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if i == 0 and isinstance(r.get("bg"), dict):
                    bg = r["bg"].get("path")
                if "ref" in r and "o" in r:
                    ref = r["ref"] if isinstance(r["ref"], str) else None
    return bg, ref


def guess_kind(path, pages=None):
    """→ {kind, why, bg, ref}. 차례: 옆 문제(문서) → 노트 이름 → 바탕·옆 PDF 이름 → 노트 폴더 → 바탕 PDF 있음 → 획 꼴(긴 획 위주 = 그림) → 메모.
    이름은 파일 이름을 폴더보다 먼저 본다(«<과목>/강의자료/…(필기).note» = 강의 필기)."""
    bg, ref = _head_ops(path)
    o = {"bg": bg, "ref": ref}
    stem = os.path.splitext(os.path.basename(path))[0]
    doc_ref = ref if ref and os.path.splitext(ref)[1].lower() in (".pdf", ".png", ".jpg", ".jpeg", ".md", ".docx", ".hwp") \
        and os.path.splitext(os.path.basename(ref))[0] != stem else None   # 가져온 원본(.sdocx)을 옆에 둔 것은 문제가 아님
    rel = os.path.relpath(os.path.abspath(path), VAULT).replace(os.sep, "/")

    def by_name(text, what):
        for k, rx in _NAME:
            m = re.search(rx, text.lower())
            if m:
                return {"kind": k, "why": f"{what} «{m.group(0)}»", **o}
    other = doc_ref or bg
    for text, what in ((stem, "이름"), (os.path.basename(other or ""), "옆·바탕 문서"), ("/".join((other or "").split("/")[:-1][::-1]), "옆·바탕 폴더"),
                       ("/".join(rel.split("/")[:-1][::-1]), "폴더")):
        r = text and by_name(text, what)
        if r:
            if doc_ref and r["kind"] == "강의 필기":
                continue
            return r
    if doc_ref:
        return {"kind": "풀이", "why": "옆 문제 " + os.path.basename(doc_ref), **o}
    if bg:
        return {"kind": "강의 필기", "why": "PDF 위 필기 " + os.path.basename(bg), **o}
    if pages is None:
        try:
            pages = load(path)[0]
        except Exception:  # noqa: BLE001
            pages = []
    ss = [s for _, _, x in pages for s in x if not s.get("dead") and not s["hl"] and len(s["pts"]) > 1]
    if not ss:
        return {"kind": "메모", "why": "빈 필기", **o}
    W = pages[0][0] or 595
    size = sorted(max(max(q[0] for q in s["pts"]) - min(q[0] for q in s["pts"]), max(q[1] for q in s["pts"]) - min(q[1] for q in s["pts"])) / W for s in ss)
    med = size[len(size) // 2]
    if med > 0.08 or (len(ss) < 40 and sum(v > 0.15 for v in size) >= max(2, len(ss) // 3)):
        return {"kind": "그림", "why": f"긴 획 위주(획 {len(ss)} · 크기 중앙 {med:.2f}쪽)", **o}
    return {"kind": "메모", "why": f"글 획 {len(ss)}", **o}


def _stroke(dr, s, k, top, col):
    pts = [(x * k, (y - top) * k) for x, y, _ in s["pts"]]
    lw = max(1, int(round(s["w"] * k * (3 if s["hl"] else 1))))
    if len(pts) == 1:
        x, y = pts[0]
        dr.ellipse([x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2], fill=col)
    else:
        dr.line(pts, fill=col, width=lw, joint="curve")


def _note_lines(pages):
    """노트 전체 줄 번호 — 쪽 차례대로 L1… (쪽마다 지금 남은 획 전부로 줄을 묶음) → [쪽마다 [{n, y0, y1}]].
    어느 범위를 그리든 같은 줄은 같은 번호다(곁창 답의 «L8» 이 앞 턴·더 본 그림·지금 화면 어디서 왔든 같은 자리)."""
    out, n = [], 1
    for _, _, ss in pages:
        ls = _lines([s for s in ss if not s.get("dead") and s["pts"]], start=n)
        n += len(ls)
        out.append(ls)
    return out


def _lines(ss, start=1):
    """획 → 줄 덩이 [{n, y0, y1}](쪽 좌표 · 위→아래). 세로로 겹치는 획을 묶고, 점·첨자처럼 작은 덩이는 가까운 줄에 붙인다."""
    spans = sorted((min(q[1] for q in s["pts"]), max(q[1] for q in s["pts"])) for s in ss if s["pts"])
    g = []
    for a, b in spans:
        if g and a < g[-1][1] - 0.3 * min(b - a, g[-1][1] - g[-1][0]):
            g[-1][1] = max(g[-1][1], b)
        else:
            g.append([a, b])
    if g:
        hs = sorted(b - a for a, b in g)
        med = hs[len(hs) // 2] or 1
        merged = []
        for a, b in g:
            if merged and ((b - a) < 0.45 * med or (merged[-1][1] - merged[-1][0]) < 0.45 * med) and a - merged[-1][1] < 0.5 * med:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        g = merged
    return [{"n": start + i, "y0": a, "y1": b} for i, (a, b) in enumerate(g)]


def _gutter(img, marks, w=64):
    """왼쪽에 번호 칸을 붙인다 — marks = [(번호, 그림 y0, 그림 y1)]."""
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    w = max(w, 16 + int(font.getlength(f"L{max([n for n, _, _ in marks] or [1])}")))   # 번호가 길어도(L1234) 칸 안
    out = Image.new("RGB", (img.width + w, img.height), "white")
    out.paste(img, (w, 0))
    dr = ImageDraw.Draw(out)
    # 줄이 촘촘하면 번호 글자가 겹쳐 한 자리에 L80–L82 가 붙어 보였다(11-23) — 번호는 겹치지 않게 아래로 밀고, 줄의 세로 범위는 오른쪽 막대로(번호 ↔ 막대 가는 선)
    nxt = 0.0
    for n, a, b in sorted(marks, key=lambda m: (m[1] + m[2]) / 2):
        mid = (a + b) / 2
        ty = max(0.0, mid - 12, nxt)
        dr.line([(w - 5, max(0, a)), (w - 5, max(a + 2, b))], fill=(0, 150, 0), width=2)
        if ty > mid - 12 + 2:
            dr.line([(w - 12, ty + 12), (w - 5, mid)], fill=(0, 150, 0), width=1)
        dr.text((4, ty), f"L{n}", fill=(0, 130, 0), font=font)
        nxt = ty + 23
    return out


def _band(img, text):
    """맨 위 설명 띠 — 그림을 읽는 쪽이 꼴(검정·회색·빨강)을 알게."""
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    out = Image.new("RGB", (img.width, img.height + 40), (245, 245, 245))
    ImageDraw.Draw(out).text((10, 8), text, fill=(60, 60, 60), font=font)
    out.paste(img, (0, 40))
    return out


# ───────── 자체 시험 ─────────
def _selftest():
    """원본 없이 만든 .note 로: 풀이(del·mv·po) · 조각 나눔 · 해시 안정 · 캐시 적중을 잰다."""
    def enc(pts):
        by = []
        def put(v):
            z = -2 * v - 1 if v < 0 else 2 * v
            while True:
                b = z & 0x7F; z //= 128
                by.append(b | (0x80 if z else 0))
                if not z:
                    break
        px = py = pp = 0
        for x, y, p in pts:
            X, Y, P = round(x * 10), round(y * 10), round(p * 255)
            put(X - px); put(Y - py); put(P - pp); px, py, pp = X, Y, P
        s = ""
        for i in range(0, len(by), 3):
            n = (by[i] << 16) | ((by[i + 1] if i + 1 < len(by) else 0) << 8) | (by[i + 2] if i + 2 < len(by) else 0)
            k = min(3, len(by) - i)
            s += B64[(n >> 18) & 63] + B64[(n >> 12) & 63] + (B64[(n >> 6) & 63] if k > 1 else "") + (B64[n & 63] if k > 2 else "")
        return s
    ok = []
    line = [(50 + i, 100 + (i % 7), 0.5) for i in range(40)]
    assert decode_pts(enc(line)) == [(round(x * 10) / 10, round(y * 10) / 10, round(p * 255) / 255) for x, y, p in line]
    ok.append("varint 왕복")
    recs = [{"note": 1, "size": [595, 842]}, {"page": "p1"}, {"page": "p2"},
            {"s": "a", "p": "p1", "t": "pen", "c": 0, "w": 0, "z": enc(line)},
            {"s": "b", "p": "p1", "t": "pen", "c": 1, "w": 1, "z": enc(line)},
            {"s": "c", "p": "p2", "t": "pen", "c": 0, "w": 0, "z": enc([(10, 3000, .5), (20, 3000, .5)])},
            {"o": "x", "del": ["b"]}, {"o": "y", "mv": ["a"], "dx": 5, "dy": 0}, {"o": "z", "po": ["p2", "p1"]}]
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "t.note")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(r) for r in recs))
        pages, _ = load(p)
        assert len(pages) == 2 and len(pages[1][2]) == 1 and pages[1][2][0]["pts"][0][0] == 55, "del·mv·po"
        assert len(pages[0][2]) == 1 and pages[0][1] >= 3000, "쪽 높이 = 획 끝까지"
        ok.append("del·mv·po·높이")
        ts, _ = render(p, os.path.join(td, "png"))
        assert [(t["page"], t["part"]) for t in ts] == [(1, 1), (2, 1)] and all(os.path.isfile(t["png"]) for t in ts)
        ok.append("조각 2 · 빈 조각 없음")
        ts2, _ = render(p, os.path.join(td, "png2"))
        assert [t["key"] for t in ts] == [t["key"] for t in ts2]
        ok.append("해시 안정")
        calls = []
        fake = lambda img: (calls.append(1) or "가짜 글", {"in": 1, "out": 1}, "")
        r1, s1 = read(ts, os.path.join(td, "c"), fake)
        r2, s2 = read(ts2, os.path.join(td, "c"), fake)
        assert s1["calls"] == 2 and s2["hit"] == 2 and len(calls) == 2 and r2[0][1] == "가짜 글"
        ok.append("캐시 적중 2/2")
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n" + json.dumps({"s": "d", "p": "p1", "t": "pen", "c": 0, "w": 0, "z": enc([(300, 400, .5), (310, 400, .5)])}))
        ts3, _ = render(p, os.path.join(td, "png3"))
        _, s3 = read(ts3, os.path.join(td, "c"), fake)
        assert s3["hit"] == 1 and s3["calls"] == 1, s3
        ok.append("덧쓴 쪽만 다시 읽음")
        sd = os.path.join(td, "seen")
        first, fi = since(p, os.path.join(td, "s0"), sd)
        assert fi["first"] and fi["pages"] == [2] and fi["new"] == 2, fi            # 마지막에 쓴 쪽 = p1(po 로 보이는 차례 2쪽) · 획 a·d
        mark(p, sd)
        none, ni = since(p, os.path.join(td, "s1"), sd)
        assert not none and ni["new"] == 0
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n" + json.dumps({"s": "e", "p": "p1", "t": "pen", "c": 0, "w": 0, "z": enc([(100, 700, .5), (140, 700, .5)])})
                    + "\n" + json.dumps({"o": "q", "del": ["d"]}))
        got, gi = since(p, os.path.join(td, "s2"), sd)
        assert gi["new"] == 1 and gi["erased"] == 1 and gi["pages"] == [2] and len(got) == 1, gi
        h = Image.open(got[0]["png"]).height
        assert h < 842 * WIDTH / 595 * 0.6, h                                     # 쪽 전체가 아니라 잘린 그림
        ok.append(f"--since 처음 쪽 · 표식 뒤 0 · 새 1 + 지운 1 · 잘림 {h}px")
        # 화면(최소 보기): 2쪽(p1) y 350~750 = 획 d 는 지워짐(빨강) · e(y700) 새것 · a(y100) 는 화면 밖 위
        sc, si = screen(p, [(2, 350, 750)], os.path.join(td, "sc"), sd)
        assert len(sc) == 1 and sc[0]["new"] == 1 and sc[0]["erased"] == 1 and sc[0]["above"] >= 1 and not si["new_off"], (sc, si)
        assert _norm_segs([(1, 2900, 3000 + 842)], si["dims"] and [(595, 3008), (595, 842)])[-1][0] == 2
        mark_segs(p, [(2, 350, 750)], sd)
        _, s2i = screen(p, [(2, 0, 842)], os.path.join(td, "sc2"), sd)
        assert s2i["new_off"] == {}, s2i
        ok.append("--screen 범위만 · 새/지움 · 위 남음 · 쪽 넘김 · 본 범위 표식")
    print("selftest 통과: " + " · ".join(ok))


def main():
    a = sys.argv[1:]
    if a[:1] == ["--selftest"]:
        return _selftest()
    if not a or a[0].startswith("-"):
        print(__doc__)
        return 2
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    page = int(opt("--page")) if "--page" in a else None
    seen_dir = opt("--seen", SEEN)
    if "--kind" in a:                        # 종류 짐작만(곁창이 열릴 때 · 사용량 0)
        print(json.dumps(guess_kind(a[0]), ensure_ascii=False))
        return 0
    if "--screen" in a:                      # 지금 화면(최소 보기) — 그림 + 한 줄 JSON · --mark = 본 범위만 표식에 더함
        segs = parse_segs(opt("--screen"))
        if "--mark" in a and "--json" not in a:
            print("표식: " + mark_segs(a[0], segs, seen_dir))
            return 0
        shots, info = screen(a[0], segs, opt("--out"), seen_dir, int(opt("--width", WIDTH)), int(opt("--start", 1)),
                             "--all" not in a, opt("--label", "지금 탭 화면"))
        if "--json" in a:
            print(json.dumps({"shots": shots, **info}, ensure_ascii=False))
        else:
            for o in shots:
                print(o["png"])
            print(json.dumps(info, ensure_ascii=False))
        if "--mark" in a:
            mark_segs(a[0], segs, seen_dir)
        return 0
    if "--since" in a or "--mark" in a:
        if "--since" in a:
            vw = None
            if "--view" in a:                # --view 쪽[,y0,y1](쪽 좌표) — 보이는 자리 전체
                v = opt("--view").split(",")
                vw = (int(v[0]), float(v[1]) if len(v) > 2 else None, float(v[2]) if len(v) > 2 else None)
            shots, info = since(a[0], opt("--out"), seen_dir, int(opt("--width", WIDTH)), vw)
            if "--json" in a:                # 실행기(노트 대화)용 — 그림 경로·줄 자리 표를 한 줄 JSON 으로
                print(json.dumps({"shots": shots, "kind": guess_kind(a[0]), **{k: v for k, v in info.items() if k != "mark"}}, ensure_ascii=False))
                if "--mark" in a:
                    mark(a[0], seen_dir)
                return 0
            for o in shots:
                print(o["png"])
            print(json.dumps({k: v for k, v in info.items() if k != "mark"}, ensure_ascii=False) if shots else "(새로 쓴 것 없음)")
        if "--mark" in a:
            print("표식: " + mark(a[0], seen_dir))
        return 0
    ts, typed = render(a[0], opt("--out"), page, int(opt("--width", WIDTH)))
    if "--read" not in a:
        for t in ts:
            print(t["png"])
        if typed:
            print("타자 글: " + " / ".join(x.replace("\n", " ")[:80] for x in typed))
        if not ts and not typed:
            print("(빈 필기)")
        return 0
    res, stat = read(ts, opt("--cache", CACHE))
    print(as_markdown(res, typed))
    print(json.dumps(stat, ensure_ascii=False), file=sys.stderr)
    return 1 if stat["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
