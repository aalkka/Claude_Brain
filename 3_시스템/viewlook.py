"""보는 화면 읽개 — 분할 화면의 칸(PDF · md · 시트 · 그림)을 «보이는 범위만» 꺼낸다(11-22 · 볼트 클로드 최소 보기).

PC 대화창(brain-base chat.ts)과 탭 곁창 실행기(notechat.cjs)가 같은 look 도구(brain-base src/viewscope.ts)로 이것을 부른다 — 두 벌 금지.
필기(.note · .sdocx)는 inkrender.py --screen 이 그린다(여기 아님). 범위 계산(위·아래·이미 본 범위 막기)은 viewscope.ts 몫이고 여기는 주어진 범위만 꺼낸다.

사용(한 줄 JSON):
  py -3 viewlook.py <파일> --info
      → PDF {kind, pages, dims[[w,h]…], text:글층 있음?} · md {kind, lines, chars} · 시트 {kind, sheets[{name, rows, cols, used}], active} · 그림 {kind, px}
  py -3 viewlook.py <PDF> --screen 쪽,y0,y1 [--as …] → 보이는 범위 중 쪽 하나 높이만 그림 + dims · shown · rest(나머지 보이는 띠 자리)
  py -3 viewlook.py <파일> --range <범위> [--as auto|img|text] [--dims]
      PDF  = 쪽,y0,y1[;쪽,y0,y1…](쪽 좌표 pt · 위에서부터) → 띠마다 글(글층이 넉넉하면) 또는 그림(긴 변 1568 · 1.15MP 안)
      md   = a-b(줄) → 줄 번호 달린 글
      시트 = 이름!A1:H30 → 값만(수식은 값으로 · 빈 칸 뺌) 칸 주소와 함께
      그림 = all → 줄인 그림
  py -3 viewlook.py --selftest
원본은 읽기만 한다.
"""
import json, math, os, re, sys, tempfile

OUT = os.path.join(tempfile.gettempdir(), "viewlook")
MAX_SIDE, MAX_PX = 1568, 1.15e6
TEXT_MIN = 120          # 띠의 글층이 이만큼(글자) 넘고 깨진 글자가 적으면 글로 — 그림보다 싸다(글 ≈ 글자/3 토큰 · 그림 ≈ w·h/750)
CELL_MAX = 600          # 시트 한 번에 내는 칸 수 상한(넘으면 앞부분 + «더 있음»)
LINE_MAX = 400          # md 한 번에 내는 줄 수 상한


def kind_of(p):
    e = os.path.splitext(p)[1].lower()
    return {".pdf": "pdf", ".md": "md", ".txt": "md", ".sheet": "sheet", ".png": "img", ".jpg": "img", ".jpeg": "img", ".webp": "img", ".gif": "img"}.get(e, "other")


def _fit(w, h):
    return min(1.0, MAX_SIDE / max(w, h), math.sqrt(MAX_PX / (w * h)))


def _save(im, tag):
    os.makedirs(OUT, exist_ok=True)
    import time
    for f in os.listdir(OUT):             # 한 시간 지난 그림은 치움(임시 폴더가 쌓이지 않게)
        q = os.path.join(OUT, f)
        try:
            if time.time() - os.path.getmtime(q) > 3600:
                os.remove(q)
        except OSError:
            pass
    f = os.path.join(OUT, f"{tag}-{os.getpid()}-{len(os.listdir(OUT))}.png")
    im.save(f)
    return f


# ───────── PDF ─────────
def pdf_info(p):
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(p)
    dims = [[round(d[i].get_width(), 1), round(d[i].get_height(), 1)] for i in range(len(d))]
    return {"kind": "pdf", "pages": len(dims), "dims": dims}   # 글층 검사는 띠마다(range) — 여기서 앞 5쪽을 훑으면 한 번에 1초 넘게 듦


def pdf_screen(p, view, how):
    """보이는 범위(쪽,y0,y1 · y1 이 쪽 높이를 넘으면 다음 쪽으로) → 먼저 쪽 하나 높이만 보이고 나머지는 자리만(rest).
    좁은 칸은 한 화면에 2쪽 넘게 보인다(11-22 잼: 7·8쪽 + 9쪽 위) — 다 그리면 필요 없는 쪽까지 그림 토큰을 쓴다."""
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(p)
    dims = [[round(d[i].get_width(), 1), round(d[i].get_height(), 1)] for i in range(len(d))]
    v = [float(x) for x in view.split(",")]
    pg, y0, left = int(v[0]), max(0.0, v[1]), max(0.0, v[2] - v[1])
    segs = []
    while left > 0.5 and 1 <= pg <= len(dims):
        H = dims[pg - 1][1]
        b = min(H, y0 + left)
        if b - y0 >= 12:
            segs.append([pg, y0, b])
        left -= b - y0
        pg, y0 = pg + 1, 0.0
    cap = dims[segs[0][0] - 1][1] if segs else 0
    shown, rest, acc = [], [], 0.0
    for s in segs:
        h = s[2] - s[1]
        if acc >= cap - 0.5:
            rest.append(s)
        elif acc + h <= cap + 0.5:
            shown.append(s)
            acc += h
        else:
            cut = s[1] + (cap - acc)
            shown.append([s[0], s[1], cut])
            rest.append([s[0], cut, s[2]])
            acc = cap
    r = pdf_range(p, ";".join(f"{a},{b},{c}" for a, b, c in shown), how) if shown else {"kind": "pdf", "pages": len(dims), "parts": []}
    r.update(dims=dims, shown=[[a, round(b), round(c)] for a, b, c in shown], rest=[[a, round(b), round(c)] for a, b, c in rest])
    return r


def _segs(spec):
    out = []
    for part in spec.split(";"):
        a = [float(x) for x in part.split(",")]
        out.append((int(a[0]), a[1] if len(a) > 1 else 0.0, a[2] if len(a) > 2 else None))
    return out


def pdf_range(p, spec, how):
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(p)
    pl = None
    try:
        import pdfplumber
        pl = pdfplumber.open(p)
    except Exception:
        pass
    res = []
    for pg, y0, y1 in _segs(spec):
        if not 1 <= pg <= len(d):
            res.append({"page": pg, "error": f"쪽은 1~{len(d)}"})
            continue
        page = d[pg - 1]
        W, H = page.get_width(), page.get_height()
        y1 = H if y1 is None else min(H, y1)
        y0 = max(0.0, min(y0, y1))
        if y1 - y0 < 1:
            continue
        txt = ""
        if pl is not None and how != "img":
            try:
                txt = (pl.pages[pg - 1].crop((0, y0, W, y1)).extract_text() or "").strip()
            except Exception:
                txt = ""
        bad = txt.count("(cid:") + txt.count("�")
        if how == "text" or (how == "auto" and len(txt) >= TEXT_MIN and bad * 20 < len(txt)):
            res.append({"page": pg, "y0": round(y0), "y1": round(y1), "text": txt or "(글층 없음 — as img 로 다시)"})
            continue
        # pt → px: 폭 = 2배(글자 또렷) · 긴 변 1568 · 넓이 1.15MP 안(넘으면 모델이 줄여 작은 글자를 잘못 읽음 — inkrender 와 같은 상한)
        sc = min(2.0, MAX_SIDE / W, MAX_SIDE / (y1 - y0), math.sqrt(MAX_PX / (W * (y1 - y0))))
        im = page.render(scale=sc, crop=(0, H - y1, 0, y0)).to_pil()   # crop = (왼, 아래, 오른, 위) 잘라낼 pt
        res.append({"page": pg, "y0": round(y0), "y1": round(y1), "png": _save(im, "pdf"), "px": list(im.size)})
    return {"kind": "pdf", "pages": len(d), "parts": res}


# ───────── md ─────────
def md_info(p):
    t = open(p, encoding="utf-8", errors="replace").read()
    return {"kind": "md", "lines": t.count("\n") + (0 if t.endswith("\n") else 1), "chars": len(t)}


def md_range(p, spec):
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", spec.strip())
    if not m:
        raise ValueError("md 범위 = a-b(줄)")
    a, b = int(m.group(1)), int(m.group(2))
    ls = open(p, encoding="utf-8", errors="replace").read().split("\n")
    a, b = max(1, a), min(len(ls), b, a + LINE_MAX - 1)
    body = "\n".join(f"{i}\t{ls[i - 1]}" for i in range(a, b + 1))
    return {"kind": "md", "lines": len(ls), "parts": [{"a": a, "b": b, "text": body}]}


# ───────── 시트(brain-sheet .sheet = md 안 ```sheet JSON) ─────────
def _sheet_json(p):
    t = open(p, encoding="utf-8").read()
    a = t.index("```sheet") + len("```sheet")
    b = t.index("```", a)
    return json.loads(t[a:b])


def col_name(c):
    s = ""
    c += 1
    while c:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return s


def col_num(s):
    n = 0
    for ch in s.upper():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _used(cd):
    rs = [int(r) for r, row in cd.items() if any(v.get("v") not in (None, "") for v in row.values())]
    cs = [int(c) for row in cd.values() for c, v in row.items() if v.get("v") not in (None, "")]
    return (max(rs) + 1, max(cs) + 1) if rs else (0, 0)


def sheet_info(p):
    j = _sheet_json(p)
    out = []
    for sid in j.get("sheetOrder", list(j["sheets"])):
        s = j["sheets"][sid]
        r, c = _used(s.get("cellData", {}))
        out.append({"name": s.get("name", sid), "rows": r, "cols": c, "used": f"A1:{col_name(max(c, 1) - 1)}{max(r, 1)}"})
    return {"kind": "sheet", "sheets": out, "active": out[0]["name"] if out else None}


def sheet_range(p, spec):
    j = _sheet_json(p)
    m = re.fullmatch(r"(?:(.+)!)?([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)", spec.strip())
    if not m:
        raise ValueError("시트 범위 = 이름!A1:H30")
    name = m.group(1)
    sheets = [j["sheets"][k] for k in j.get("sheetOrder", list(j["sheets"]))]
    s = next((x for x in sheets if x.get("name") == name), None) if name else sheets[0]
    if s is None:
        raise ValueError("시트 이름: " + " · ".join(x.get("name", "") for x in sheets))
    c0, r0, c1, r1 = col_num(m.group(2)), int(m.group(3)) - 1, col_num(m.group(4)), int(m.group(5)) - 1
    cd = s.get("cellData", {})
    rows, n, more = [], 0, False
    for r in range(r0, r1 + 1):
        row = cd.get(str(r), {})
        cells = []
        for c in range(c0, c1 + 1):
            v = row.get(str(c), {}).get("v")
            if v in (None, ""):
                continue
            if n >= CELL_MAX:
                more = True
                break
            v = round(v, 6) if isinstance(v, float) else v
            cells.append(f"{col_name(c)}{r + 1}={v}")
            n += 1
        if cells:
            rows.append(" | ".join(cells))
        if more:
            break
    return {"kind": "sheet", "sheet": s.get("name"), "parts": [{"range": spec, "text": "\n".join(rows) + ("\n…(칸이 더 있음 — 범위를 좁혀 다시)" if more else ""), "cells": n}]}


# ───────── 그림 ─────────
def img_range(p):
    from PIL import Image
    im = Image.open(p)
    im.load()
    f = _fit(*im.size)
    if f < 1:
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))))
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    return {"kind": "img", "parts": [{"png": _save(im, "img"), "px": list(im.size)}]}


def info(p):
    k = kind_of(p)
    if k == "pdf":
        return pdf_info(p)
    if k == "md":
        return md_info(p)
    if k == "sheet":
        return sheet_info(p)
    if k == "img":
        from PIL import Image
        return {"kind": "img", "px": list(Image.open(p).size)}
    return {"kind": k}


def rng(p, spec, how="auto"):
    k = kind_of(p)
    if k == "pdf":
        return pdf_range(p, spec, how)
    if k == "md":
        return md_range(p, spec)
    if k == "sheet":
        return sheet_range(p, spec)
    if k == "img":
        return img_range(p)
    raise ValueError(f"이 종류는 못 읽음: {k}")


def selftest():
    d = tempfile.mkdtemp()
    f = os.path.join(d, "a.md")
    open(f, "w", encoding="utf-8").write("\n".join(f"줄{i}" for i in range(1, 51)))
    assert md_info(f)["lines"] == 50
    r = md_range(f, "3-5")["parts"][0]
    assert r["text"].split("\n")[0] == "3\t줄3" and r["b"] == 5
    assert col_name(0) == "A" and col_name(27) == "AB" and col_num("AB") == 27
    s = os.path.join(d, "s.sheet")
    open(s, "w", encoding="utf-8").write('---\n\n```sheet\n{"sheetOrder":["x"],"sheets":{"x":{"name":"표","cellData":{"0":{"0":{"v":"이름"},"1":{"v":2.5}},"3":{"2":{"v":7}}}}}}\n```\n')
    i = sheet_info(s)
    assert i["sheets"][0]["used"] == "A1:C4", i
    t = sheet_range(s, "표!A1:C4")["parts"][0]["text"]
    assert t == "A1=이름 | B1=2.5\nC4=7", t
    print("selftest 통과")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "--selftest":
        selftest()
        sys.exit(0)
    p = a[0]
    try:
        how = a[a.index("--as") + 1] if "--as" in a else "auto"
        if "--info" in a:
            r = info(p)
        elif "--screen" in a:
            r = pdf_screen(p, a[a.index("--screen") + 1], how)
        else:
            r = rng(p, a[a.index("--range") + 1], how)
            if r.get("kind") == "pdf" and "--dims" in a:
                r["dims"] = pdf_info(p)["dims"]
    except Exception as e:
        r = {"error": f"{type(e).__name__}: {e}"}
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False))
