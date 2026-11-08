"""ingest.py 시험 — 글자 차례 복원 · OCR 방향 보정 · pptx 그림 한 장이 문서를 죽이지 않기(11-05). 합성 파일만 쓴다(볼트를 안 건드림 · OCR 은 가짜).
  py -3 3_시스템/_eval/ingest_check.py
"""
import io
import json
import os
import re
import sys
import tempfile
import zipfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ingest  # noqa: E402

bad = 0


def ok(name, cond, extra=""):
    global bad
    print(("통과" if cond else "실패"), name, extra if not cond else "")
    bad += 0 if cond else 1


def make_pdf(ops):
    """글자를 ops [(x, y, 글 | (앞 글, 건너뛸 pt, 뒤 글))] 차례 그대로 쓴 한 쪽 PDF(Helvetica).
    튜플 = 글 상자 하나가 한 줄을 건너뛰며 쓴 것 — pdfium 은 글 상자 시작 x 로는 줄 안을 정렬하므로 상자가 겹칠 때만 뒤섞인다(Print To PDF 꼴)."""
    def show(t):
        return f"({t}) Tj" if isinstance(t, str) else f"[({t[0]}) {-t[1] * 1000 // 12} ({t[2]})] TJ"
    body = "".join(f"BT /F1 12 Tf 1 0 0 1 {x} {y} Tm {show(t)} ET\n" for x, y, t in ops).encode()
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            b"<</Length %d>>stream\n%s\nendstream" % (len(body), body), b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, off = bytearray(b"%PDF-1.7\n"), []
    for i, o in enumerate(objs, 1):
        off.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % x for x in off)
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


td = tempfile.mkdtemp(prefix="ingest-check-")
ingest.OCR_CACHE = os.path.join(td, "ocr")


def pdf_body(name, ops):
    p = os.path.join(td, name)
    with open(p, "wb") as f:
        f.write(make_pdf(ops))
    return ingest.ex_pdf(p, "1_수집/x.pdf", name)


# ── 글자 차례 ──
# 한 줄을 글꼴별로 나눠 쓴 문서(hwp → Print To PDF 꼴): 앞·뒤를 먼저 쓰고 가운데를 나중에
jumbled = [op for y in range(700, 500, -20) for op in ((100, y, (f"aaa{y}", 60, f"ccc{y}")), (146, y, f"bbb{y}"))]
b, m, q = pdf_body("jumbled.pdf", jumbled)
ok("뒤섞인 줄이 위치 차례로", all(f"aaa{y} bbb{y} ccc{y}" in b for y in range(700, 500, -20)), b[:200])
ok("품질 줄에 복원 표시", "글자 차례 복원 1/1쪽" in q and q.startswith("ok"), q)

# 두 단 + 줄 안 뒤섞임: 왼쪽 단이 끝난 뒤 오른쪽 단(위에서 아래로 다시 늘어놓으면 단이 섞인다)
cols = [op for x0 in (72, 320) for y in range(700, 560, -20) for op in ((x0, y, (f"h{x0}y{y}", 60, f"t{x0}y{y}")), (x0 + 50, y, f"m{x0}y{y}"))]
b, _, q = pdf_body("cols.pdf", cols)
pos = [b.find(f"h72y{y}") for y in range(700, 560, -20)] + [b.find(f"h320y{y}") for y in range(700, 560, -20)]
ok("두 단이 안 섞임", -1 not in pos and pos == sorted(pos), b[:300])
ok("두 단 복원됨", "글자 차례 복원" in q and "h72y700 m72y700 t72y700" in b, q + b[:200])

# 멀쩡한 문서 = 쓴 차례 그대로(복원 안 함) · 표 칸이 줄마다 왼쪽→오른쪽
plain = [(100, y, f"line{y}") for y in range(700, 400, -15)]
b, _, q = pdf_body("plain.pdf", plain)
ok("멀쩡한 문서는 안 건드림", "글자 차례" not in q and q.startswith("ok"), q)
b2, _, q2 = pdf_body("one-back.pdf", plain + [(300, 700, "x"), (100, 400, "y")])
ok("뒤로 돌아감이 드문 문서도 안 건드림(수식 쪽 꼴)", "글자 차례" not in q2, q2)

# ── OCR 방향 ──
KO = ["선발 대상은 학부 재학생으로 합니다", "제출 서류는 성적증명서와 재학증명서입니다", "기한 안에 온라인으로 신청하시기 바랍니다"]
BAD = ["1卜1卜", "=1卜", "窿K10犁", "끄卜 窅0 1卜", "謚「 61 피」", "爻0", "」10宿」", "夜「叉0", "犁7", "쁘「끄卜", "苞0 패」", "켄K10犁"]
LABEL = ["Voltage across capacitor Vc"]                   # 세로 축 이름만 바로 읽히는 쪽
HAND = ["1 r 5ó", "〈뙤 C", "6」 犁", "a 4아4", "6 j", "해] 40」", "q6「 窅0"]
ok("판별: 깨진 쪽 의심", ingest.looks_turned(1, BAD))
ok("판별: 멀쩡한 쪽 안 의심", not ingest.looks_turned(1, KO))
ok("판별: 작은 그림은 의심 안 함", not ingest.looks_turned("img:ab", ["a1", "b"]))
ok("고르기: 바른 방향", ingest.pick_turn(BAD, [(90, BAD), (180, BAD), (270, KO)]) == 270)
ok("고르기: 어느 방향도 안 읽히면 그대로(손글씨)", ingest.pick_turn(HAND, [(90, HAND), (180, BAD), (270, HAND)]) == 0)
page = ["Figure 3 shows the output 1 0 1 1 of the 2 bit adder and 3 4 x y z"] * 3
ok("고르기: 글이 더 많은 쪽을 축 이름 몇 글자로 안 밀어냄", ingest.pick_turn(page, [(90, BAD), (180, BAD), (270, LABEL)]) == 0)
ok("고르기: 다 실패면 다음에", ingest.pick_turn(BAD, [(90, None), (180, None), (270, None)]) is None)


def fake_ocr(script):
    """파일 이름의 돌린 각도로 답을 고르는 가짜 엔진 — 호출마다 받은 장 수를 적는다."""
    calls = []

    def run(pngs):
        calls.append(len(pngs))
        ingest.OCR_ENGINE = "가짜"
        if script.get("die") and len(calls) > script["die"]:
            return None, "엔진 죽음"
        return [script.get(re.search(r"\.(\d+)\.png$", p).group(1) if re.search(r"\.(\d+)\.png$", p) else "0", BAD) for p in pngs], None
    return run, calls


def render(_, out):
    from PIL import Image
    Image.new("RGB", (40, 30), "white").save(out)


real_ocr = ingest.ocr_images
ingest.ocr_images, calls = fake_ocr({"0": BAD, "270": KO})
got, why, _ = ingest.ocr_cached("rot1", [1], render)
ok("깨진 쪽 → 돌린 글로 바뀜", got[1] == KO, got)
ok("첫 읽기 1 + 세 방향 3", calls == [1, 3], calls)
c = json.load(open(os.path.join(ingest.OCR_CACHE, "rot1.json"), encoding="utf-8"))
ok("캐시에 각도", c.get("rot") == {"1": 270} and c["pages"]["1"] == KO, c)
got, _, _ = ingest.ocr_cached("rot1", [1], render)
ok("다시 불러도 안 읽음", calls == [1, 3] and got[1] == KO, calls)

ingest.ocr_images, calls = fake_ocr({"0": KO})
got, _, _ = ingest.ocr_cached("rot2", [1], render)
ok("멀쩡한 쪽은 한 번만 읽음", calls == [1] and got[1] == KO, calls)

ingest.ocr_images, calls = fake_ocr({"0": HAND, "90": HAND, "180": HAND, "270": HAND})
got, _, _ = ingest.ocr_cached("rot3", [1], render)
ingest.ocr_cached("rot3", [1], render)
ok("안 읽히는 쪽은 그대로 · 한 번만 돌려 봄", got[1] == HAND and calls == [1, 3], calls)

os.makedirs(ingest.OCR_CACHE, exist_ok=True)
with open(os.path.join(ingest.OCR_CACHE, "rot4.json"), "w", encoding="utf-8") as f:
    json.dump({"engine": "옛", "dpi": ingest.OCR_DPI, "pages": {"1": BAD, "2": KO}}, f)
ingest.ocr_images, calls = fake_ocr({"270": KO})
got, _, _ = ingest.ocr_cached("rot4", [1, 2], render)
ok("옛 캐시의 깨진 쪽만 다시", calls == [3] and got[1] == KO and got[2] == KO, calls)

ingest.ocr_images, calls = fake_ocr({"0": BAD, "die": 1})
got, why, _ = ingest.ocr_cached("rot5", [1], render)
c = json.load(open(os.path.join(ingest.OCR_CACHE, "rot5.json"), encoding="utf-8"))
ok("돌려 읽다 엔진이 죽으면 첫 글 유지 · 다음에 다시", got[1] == BAD and "rot" not in c and why, c)


# ── pptx 그림 ──
def deck(mutate):
    import pptx
    from PIL import Image
    im = io.BytesIO()
    Image.new("RGB", (60, 40), "white").save(im, "PNG")
    im.seek(0)
    prs = pptx.Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "제목 글자"
    s.shapes.add_picture(im, 0, 0)
    tb = s.shapes.add_textbox(0, 0, 100, 100)
    tb.text = "본문 글자"
    buf = io.BytesIO()
    prs.save(buf)
    src = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for n in src.namelist():
            name, data = mutate(n, src.read(n))
            z.writestr(name, data)
    return out.getvalue()


def unknown_type(n, d):
    """파일이 그림 형식을 image/unknown 으로 밝힌 경우(속은 PNG)."""
    if n == "[Content_Types].xml":
        d = d.replace(b'Extension="png" ContentType="image/png"', b'Extension="bin" ContentType="image/unknown"')
    elif n.startswith("ppt/slides/_rels/"):
        d = re.sub(rb"(media/image\d+)\.png", rb"\1.bin", d)
    return re.sub(r"(media/image\d+)\.png$", r"\1.bin", n), d


def junk_emf(n, d):
    """PIL 이 못 여는 바이트(EMF 꼴)."""
    if n.endswith(".png") and "media/" in n:
        d = b"\x01\x00\x00\x00 not a picture"
    if n == "[Content_Types].xml":
        d = d.replace(b'Extension="png" ContentType="image/png"', b'Extension="emf" ContentType="image/x-emf"')
    elif n.startswith("ppt/slides/_rels/"):
        d = re.sub(rb"(media/image\d+)\.png", rb"\1.emf", d)
    return re.sub(r"(media/image\d+)\.png$", r"\1.emf", n), d


def linked(n, d):
    """바깥 파일로 링크한 그림(r:embed 없음)."""
    if re.fullmatch(r"ppt/slides/slide\d+\.xml", n):
        d = d.replace(b"r:embed=", b"r:link=")
    return n, d


ingest.ocr_images, calls = fake_ocr({"0": ["그림 속 글자입니다"]})
for i, (label, mut) in enumerate((("형식 모름(속은 PNG)", unknown_type), ("못 여는 그림", junk_emf), ("링크 그림", linked), ("보통 그림", lambda n, d: (n, d)))):
    p = os.path.join(td, f"deck{i}.pptx")
    with open(p, "wb") as f:
        f.write(deck(mut))
    try:
        b, m, q = ingest.ex_markitdown(p, "1_수집/x.pptx", ".pptx", f"deck{i}")
    except Exception as e:
        b, q = "", f"{type(e).__name__}: {e}"
    ok(f"pptx {label}: 본문이 나옴", "제목 글자" in b and "본문 글자" in b and q.startswith("ok"), q)
    if mut is unknown_type:
        ok("pptx 형식 모름: 그림 속 글자도 읽음", "그림 속 글자입니다" in b, b[:200])

ingest.ocr_images = real_ocr
print("== 실패", bad)
sys.exit(1 if bad else 0)
