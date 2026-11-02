"""손글씨 위치 — 그림 읽기가 옮긴 판서를 쪽 위 낱말 상자로. brain-source 가 PDF 위에 보이지 않는 글자 층으로 덧씌운다
(판서 끌어 고르기 · 사용자 11-02). ingest.py --vision 이 부른다(numpy 만 · Claude 호출은 ingest_vision.read_boxes).

방법(v2 · 11-02):
  ①잉크 = 흰 바탕에서 어둡거나 색 있는 픽셀(형광펜·괘선 빼기) → XY 자르기(빈 행·빈 열로 거듭 나눔)로 낱말 조각
     → 같은 줄에서 가까운 조각을 이어 «글 덩이»(대개 판서 한 줄 · 그림은 꼬리표째 한 덩이)
  ②덩이에 번호를 그린 그림 → Claude 가 번호마다 그 안의 글을 옮겨 적음(ingest_vision.read_boxes · 그림이면 «#») — 전사와 위치가 한 호출
     → 위치는 잉크에서 · 글은 글씨를 읽는 쪽이 정한다. 2쪽(그림·꼬리표 많음) 입력 3,843 + 출력 688 토큰
  ③덩이 안 = 낱말마다: 글자 무게 비례로 낱말 경계를 잡고 가장 가까운 잉크 틈에 붙인다(사용량 0)
기각(11-02 실측): v1 = 전사 줄을 잉크 덩이에 너비만으로 짝지음(사용량 0) — 그림 꼬리표 줄(σ+ · -Q)이 옆 문장 낱말 덩이에
  붙고 한 줄에 꼬리표 다섯 줄이 겹침(2쪽) → 사용자 «보이는 글자와 선택되는 글자가 다름 · 아예 다른 글자». 윈도우 OCR 줄 상자
  (판서 줄 절반을 못 찾음 · 인식기 = ko 하나) · Claude 에게 좌표 묻기(상자가 한 줄씩 밀림).

사용:  py -3 3_시스템/hwlayout.py <그림> <출력 png>     # 글 덩이 번호 그림(Claude 에 보내는 것과 같음)
"""
import io
import math
import numpy as np

VERSION = 2                 # 위치 형식(pos.v) — 2 가 아니면 플러그인은 덧씌우지 않고 «그림 읽기» 가 위치만 다시 읽는다


def ink_mask(a):
    r, g, b = (a[..., i].astype(np.int16) for i in range(3))
    mn, mx = np.minimum(np.minimum(r, g), b), np.maximum(np.maximum(r, g), b)
    yellow = (r > 190) & (g > 180) & (b < 140)          # 형광펜 — 글씨가 아니다
    return ((mn < 140) | ((mx - mn > 90) & (mx < 235))) & ~yellow


def runs(v, gap):
    """참인 칸의 [시작, 끝) 구간 — gap 이하 틈은 잇는다"""
    idx = np.flatnonzero(v)
    if not len(idx):
        return []
    cut = np.flatnonzero(np.diff(idx) > gap + 1)
    starts = np.r_[idx[0], idx[cut + 1]]
    ends = np.r_[idx[cut] + 1, idx[-1] + 1]
    return list(zip(starts.tolist(), ends.tolist()))


def ink(img):
    """(잉크 마스크, 보통 줄 높이 px)"""
    m = ink_mask(np.asarray(img.convert("RGB")))
    H, W = m.shape
    m[m.sum(1) > 0.6 * W] = False                       # 가로 괘선
    hs = sorted(e - s for s, e in runs(m.sum(1) > 1, max(2, H // 400)) if e - s > 3)
    return m, (hs[len(hs) // 2] if hs else 20)


def _xycut(m, x0, y0, rg, cg, out):
    ys, xs = np.flatnonzero(m.sum(1)), np.flatnonzero(m.sum(0))
    if not len(ys):
        return
    m = m[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]
    x0, y0 = x0 + int(xs[0]), y0 + int(ys[0])
    for axis in (1, 0):                                  # 빈 행으로 먼저, 안 되면 빈 열로
        parts = runs(m.sum(axis) > 0, rg if axis == 1 else cg)
        if len(parts) > 1:
            for s, e in parts:
                if axis == 1:
                    _xycut(m[s:e], x0, y0 + s, rg, cg, out)
                else:
                    _xycut(m[:, s:e], x0 + s, y0, rg, cg, out)
            return
    if m.sum() >= 12:                                    # 티끌 빼기
        out.append([x0, y0, x0 + m.shape[1], y0 + m.shape[0]])


def phrases(m, lh):
    """글 덩이 [x1, y1, x2, y2](px) — 읽는 순서(가운데 y 로 줄 묶음 → 왼→오)"""
    leaves = []
    _xycut(m, 0, 0, 2, max(6, int(lh * 0.3)), leaves)
    # 세로로 겹치고(작은 쪽 높이 절반 이상) 가로 틈이 좁은(1.2 줄 높이 미만) 두 조각을 이을 것이 없을 때까지 잇는다 — 키가 큰
    # 덩이(2.2 줄 높이 이상 = 여러 줄·그림)는 옆과 잇지 않는다. 한 쪽 조각 100~250개 · 0.4초 안(11-02 실측)
    leaves.sort(key=lambda b: b[0])
    merged = True
    while merged:
        merged = False
        for i in range(len(leaves)):
            for j in range(len(leaves)):
                if i == j:
                    continue
                a, b = leaves[i], leaves[j]
                ov = min(a[3], b[3]) - max(a[1], b[1])
                gap = max(a[0], b[0]) - min(a[2], b[2])
                if ov >= 0.5 * min(a[3] - a[1], b[3] - b[1]) and gap < 1.2 * lh and max(a[3] - a[1], b[3] - b[1]) < 2.2 * lh:
                    leaves[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    del leaves[j]
                    merged = True
                    break
            if merged:
                break
    cy = lambda b: (b[1] + b[3]) / 2
    leaves.sort(key=cy)
    rows, cur = [], []
    for b in leaves:
        if cur and cy(b) - cy(cur[-1]) > lh * 0.6:
            rows.append(cur)
            cur = []
        cur.append(b)
    if cur:
        rows.append(cur)
    return [b for r in rows for b in sorted(r, key=lambda b: b[0])]


def marked(img, boxes):
    """덩이마다 파란 상자 + 빨간 번호(왼쪽 위 바깥)를 그린 PNG 바이트 — Claude 에게 보낸다"""
    from PIL import ImageDraw, ImageFont
    mk = img.convert("RGB")
    d = ImageDraw.Draw(mk)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for i, (x1, y1, x2, y2) in enumerate(boxes):
        d.rectangle([x1 - 1, y1 - 1, x2 + 1, y2 + 1], outline=(0, 160, 255), width=1)
        t = str(i + 1)
        tw = d.textlength(t, font=font)
        tx, ty = max(0, x1 - tw - 2), y1 - 3
        d.rectangle([tx - 1, ty, tx + tw + 1, ty + 14], fill=(255, 255, 255))
        d.text((tx, ty), t, fill=(220, 0, 0), font=font)
    b = io.BytesIO()
    mk.save(b, "PNG")
    return b.getvalue()


def weight(t):
    """너비 추정(보통 글자 = 1) — 아래·위 첨자는 반, 빈칸·문장부호는 덜"""
    w, small = 0.0, False
    for ch in t:
        if ch in "_^":
            small = True
            continue
        c = 0.45 if ch == " " else 0.5 if ch in "·.,:;'|()" else 1.0
        w += c * (0.5 if small else 1.0)
        if not ch.isalnum():
            small = False
    return max(w, 0.5)


def words(m, box, text, lh):
    """덩이 하나의 글 → 낱말마다 (x1, y1, x2, y2, 낱말) px. 낱말 경계 = 글자 무게 비례 자리에서 가장 가까운 잉크 틈(순서 지킴)"""
    x1, y1, x2, y2 = box
    toks = text.split()
    if len(toks) <= 1:
        return [(x1, y1, x2, y2, text.strip())]
    sub = m[y1:y2, x1:x2]
    cols = sub.sum(0) > 0
    gaps = [((s + e) / 2, e - s) for s, e in runs(~cols, 0) if s > 0 and e < len(cols)]   # 잉크 사이 빈 열(가운데, 너비)
    # 낱말 사이 틈은 글자 사이 틈보다 넓다 — 넓은 틈 (낱말 수 − 1) + 여유만 후보로(무게 비례만으로는 경계가 반 낱말씩 밀렸다 · 2쪽)
    keep = max(len(toks) - 1 + max(2, (len(toks) - 1) // 3), 0)
    gaps = sorted(sorted(gaps, key=lambda q: -q[1])[:keep])
    ws = [weight(t) for t in toks]
    tot = sum(ws) + 0.45 * (len(toks) - 1)
    ideal, acc = [], 0.0
    for w in ws[:-1]:
        acc += w + 0.45 / 2
        ideal.append(acc / tot * (x2 - x1))
        acc += 0.45 / 2
    n, g = len(ideal), len(gaps)
    cut = list(ideal)
    if g >= n:                                           # 경계 i → 틈 j(늘게) · 비용 = 떨어진 거리 − 넓은 틈 덤
        cost = lambda i, j: abs(ideal[i] - gaps[j][0]) / lh - 1.0 * min(gaps[j][1] / lh, 1.0)
        INF = math.inf
        f = [[INF] * g for _ in range(n)]
        bk = [[0] * g for _ in range(n)]
        for j in range(g):
            f[0][j] = cost(0, j)
        for i in range(1, n):
            best, arg = INF, 0
            for j in range(i, g):
                if f[i - 1][j - 1] < best:
                    best, arg = f[i - 1][j - 1], j - 1
                f[i][j] = best + cost(i, j)
                bk[i][j] = arg
        j = min(range(n - 1, g), key=lambda j: f[n - 1][j])
        for i in range(n - 1, -1, -1):
            cut[i] = gaps[j][0]
            j = bk[i][j]
    edges = [0.0] + cut + [float(x2 - x1)]
    spans = []                                           # 낱말마다 (잉크 왼쪽, 잉크 오른쪽, 위, 아래)
    for a, b in zip(edges, edges[1:]):
        a, b = int(round(a)), max(int(round(b)), int(round(a)) + 1)
        xs, rows = np.flatnonzero(sub[:, a:b].sum(0)), np.flatnonzero(sub[:, a:b].sum(1))
        spans.append((a + int(xs[0]), a + int(xs[-1]) + 1, int(rows[0]), int(rows[-1]) + 1) if len(xs) else (a, b, 0, y2 - y1))
    # 글자 상자 = 낱말 잉크 왼쪽 ~ 다음 낱말 잉크 왼쪽(뒤 빈칸이 틈을 덮는다) — 틈 가운데부터 놓으면 보이지 않는 첫 글자가
    # 잉크보다 반 틈 앞에 와서 낱말 첫 글자가 안 골라졌다(시험 «theorem» → «heorem»)
    out = []
    for i, (t, (l, r, ya, yb)) in enumerate(zip(toks, spans)):
        right = spans[i + 1][0] if i + 1 < len(spans) else r
        out.append((x1 + l, y1 + ya, x1 + max(right, l + 1), y1 + yb, t))
    return out


def layout(img, boxes, texts):
    """글 덩이 + 덩이마다 글(None = 그림) → pos.items: [x1, y1, x2, y2, 글, 줄끝(0/1)](쪽 비율) — 낱말마다 하나, 덩이 끝 = 줄끝"""
    m, lh = ink(img)
    H, W = m.shape
    items = []
    for box, text in zip(boxes, texts):
        if not text:
            continue
        ws = words(m, box, text, lh)
        for i, (a, b, c, d, t) in enumerate(ws):
            last = i == len(ws) - 1
            items.append([round(a / W, 4), round(b / H, 4), round(c / W, 4), round(d / H, 4), t if last else t + " ", int(last)])
    return items


if __name__ == "__main__":
    import sys
    from PIL import Image
    im = Image.open(sys.argv[1]).convert("RGB")
    m, lh = ink(im)
    bx = phrases(m, lh)
    open(sys.argv[2], "wb").write(marked(im, bx))
    print(f"줄 높이 {lh} · 글 덩이 {len(bx)}")
