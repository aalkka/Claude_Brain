"""원본 색인 생성기 — 1_수집 원본마다 1_수집/_색인/<원본 상대경로>.색인.md 를 만든다.

색인 = 정리본이 아니라 «찾고 원본의 그 자리로 가기 위한» 검색 표면. 옵시디언 검색과 search.py 가 같은 파일을 읽는다.
규칙 = 3_시스템/conventions.md §원본·색인 · 설계 = 2_지식/notes/외부뇌-원본형식-수용.md · 결정 = ADR-013.

사용:
  py -3 3_시스템/ingest.py                 1_수집 전체 — 바뀐 것만 다시 만든다
  py -3 3_시스템/ingest.py <파일|폴더>...   지정분만(같은 해시 묶음은 전체를 보고 정한다)
  --force   해시·판이 같아도 다시 만든다
  --dry     쓰지 않고 할 일만 보고
  --prune   원본이 없어진 색인(고아)을 지운다(기본은 보고만)
  --vision  그림 쪽(글자 층 20자 미만)·그림 파일을 Claude(claude -p · sonnet 5.5)로 읽어 «그림 키워드 + 손글씨» 를 색인에 덧붙인다.
            사용량이 들어서 이 플래그를 줄 때만 부른다. 결과 캐시 = 3_시스템/_index/ingest-vision/ · 글씨체 사전 = 3_시스템/handwriting/

원칙:
  - 원본은 읽기만 한다. 메모 md(원본 옆)는 절대 쓰지 않는다.
  - 같은 sha256 = 색인 하나(`also` 에 다른 경로). 원본이 옮겨지면 해시로 다시 잇는다.
  - 생략·요약하지 않는다. 예외 = 표(xlsx·csv)는 표마다 TABLE_ROWS 행, 텍스트는 TEXT_LINES 줄까지(숫자 행은 검색 잡음 · 원천은 원본).
"""
import argparse, hashlib, json, os, re, sys, time, zipfile, zlib
from datetime import date
from urllib.parse import quote

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(VAULT, "1_수집")
OUT = os.path.join(SRC, "_색인")
VERSION = "ingest 0.3"   # 판을 올리면 모든 색인을 다시 만든다(0.2 = 제목 줄 · 0.3 = OCR)
SUFFIX = ".색인.md"
BIG = 50 * 1024 * 1024          # pre-commit 이 git 에서 빼는 크기
TABLE_ROWS = 200
TEXT_LINES = 5000

PDF = {".pdf"}
MARKITDOWN = {".docx", ".pptx", ".xlsx", ".xls", ".html", ".htm", ".csv", ".epub", ".ipynb"}
HWP = {".hwp", ".hwpx"}
TEXT = {".txt", ".v", ".sv", ".vhd", ".py", ".c", ".h", ".cpp", ".js", ".ts", ".json", ".tsv",
        ".log", ".m", ".tex", ".typ", ".ps1", ".sh", ".xml", ".yaml", ".yml", ".ini", ".cfg"}
IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".avif", ".svg"}
MEDIA = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".wmv", ".ogv",
         ".mp3", ".m4a", ".wav", ".flac", ".ogg", ".3gp"}

# OCR = 윈도우 내장 Windows.Media.Ocr(설치 0 · 오프라인).
# 결과는 원본 sha256 별로 캐시한다 — 판을 올려 색인을 다시 만들어도 OCR 은 다시 돌지 않는다.
OCR_DPI = 300
OCR_MAX = 10000                  # OcrEngine.MaxImageDimension(10-14 실측 · 인식기 = ko 하나)
OCR_CACHE = os.path.join(VAULT, "3_시스템", "_index", "ingest-ocr")


def rel(p):
    return os.path.relpath(p, VAULT).replace(os.sep, "/")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def index_path(origin):
    """'1_수집/학교/x.pdf' → <vault>/1_수집/_색인/학교/x.pdf.색인.md"""
    sub = origin.split("/", 1)[1]
    return os.path.join(OUT, *sub.split("/")) + SUFFIX


# ───────── 프론트매터 (값은 JSON 표기 = 유효한 YAML 이중따옴표) ─────────
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def read_fm(path):
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
    except OSError:
        return None
    m = FM_RE.match(txt)
    if not m:
        return None
    d = {}
    for ln in m.group(1).splitlines():
        k, _, v = ln.partition(":")
        v = v.strip()
        try:
            d[k.strip()] = json.loads(v)
        except ValueError:
            d[k.strip()] = v
    return d


def dump_fm(d):
    plain = {"type", "source", "confidence", "status", "created", "updated"}
    lines = ["---"]
    for k, v in d.items():
        if v is None:
            continue
        lines.append(f"{k}: {v}" if k in plain else f"{k}: {json.dumps(v, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ───────── 본문 정리 ─────────
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f﻿￾￿]")
MAX_CHARS = 2_000_000           # 안전판: 8MB 라이선스 html 실측(10-14) — 색인 하나가 옵시디언·검색을 무겁게 하지 않게


def neutralize(ln):
    """옵시디언 문법 오인 방지: %% 주석 · [[ ]] 링크(원본 글자가 링크·주석으로 사라지지 않게)."""
    return ln.replace("%%", r"\%\%").replace("[[", r"\[\[").replace("]]", r"\]\]")


def clean_plain(text):
    """추출 글(PDF·HWP): 제어 문자 제거 · 머리글 오인(#) 방지 · 빈 줄 압축."""
    text = CTRL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    out = []
    for ln in text.split("\n"):
        ln = neutralize(ln.rstrip())
        out.append(re.sub(r"^(\s{0,3})#", r"\1\\#", ln))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


OFFICE_AUTO_ALT = re.compile(r"!\[[^\]]*(?:자동 생성된 설명|[Dd]escription automatically generated)[^\]]*\]")


def clean_md(text):
    """markitdown 출력(이미 마크다운): 머리글은 살리고 제어 문자·주석·링크만.
    그림의 Office 자동 대체 텍스트(«텍스트, 폰트, 스크린샷…이(가) 표시된 사진 자동 생성된 설명»)는 뺀다 — Word·PowerPoint 가 그림만 보고
    단 것이라 그림 내용과 동떨어진 낱말이 검색에 걸린다(10-22 실사용: 회로 개념도 색인에 «폰트, 스크린샷» 이 걸렸다)."""
    text = CTRL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = OFFICE_AUTO_ALT.sub("![]", text)
    text = re.sub(r"data:[a-z]+/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]{64,}", "data:…", text)
    text = "\n".join(neutralize(ln.rstrip()) for ln in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def cap_tables(md):
    out, run, dropped = [], 0, 0
    for ln in md.split("\n"):
        if ln.startswith("|"):
            run += 1
            if run > TABLE_ROWS + 2:          # 머리줄 + 구분줄 + TABLE_ROWS 행
                dropped += 1
                continue
        else:
            if dropped:
                out.append(f"\n> (표 {dropped}행 생략 — 원본 참조)\n")
            run, dropped = 0, 0
        out.append(ln)
    if dropped:
        out.append(f"\n> (표 {dropped}행 생략 — 원본 참조)")
    return "\n".join(out)


def link(origin, label, sub=""):
    """원본 링크. 이름에 위키링크를 깨는 글자가 있으면 마크다운 링크로."""
    if re.search(r"[\[\]#|^]", origin):
        return f"[{label}]({quote(origin)}{sub})"
    return f"[[{origin}{sub}|{label}]]"


# ───────── OCR — 윈도우 내장 엔진(파워셸 5.1 한 번 띄워 여러 장) ─────────
# WinRT 프로젝션은 Windows PowerShell 5.1 만 준다(pwsh 7 안 됨 — 눈 eye/ocr.py 와 같은 제약).
_OCR_PS = r'''
param([string]$List)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$null = [Windows.Media.Ocr.OcrEngine,Windows.Media,ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
  $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new("ko"))
if ($engine -eq $null) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($engine -eq $null) { [Console]::Out.WriteLine("NOENGINE"); exit }
[Console]::Out.WriteLine("READY " + $engine.RecognizerLanguage.LanguageTag)
foreach ($p in [System.IO.File]::ReadAllLines($List, [System.Text.Encoding]::UTF8)) {
  if (-not $p) { continue }
  try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
    $o = [ordered]@{ ok = $true; lines = @(@($res.Lines) | ForEach-Object { $_.Text }) }
    $bmp.Dispose(); $stream.Dispose()
  } catch { $o = [ordered]@{ ok = $false; err = $_.Exception.Message } }
  [Console]::Out.WriteLine((ConvertTo-Json $o -Compress))
}
'''
_PS = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
OCR_ENGINE = None                # 첫 호출 뒤 "Windows.Media.Ocr <언어>"


def ocr_images(pngs):
    """PNG 경로 목록 → 줄 목록의 목록. 장마다 실패면 None. 엔진이 없거나 죽으면 (None, 까닭).

    실패는 «글자 없음» 이 아니다 — None 을 0줄로 바꾸지 않는다(눈 ocr.py 의 fail-open 과 같은 원칙).
    """
    global OCR_ENGINE
    import subprocess, tempfile
    if not os.path.exists(_PS):
        return None, "Windows PowerShell 5.1 없음"
    with tempfile.TemporaryDirectory(prefix="ingest-ocr-") as td:
        ps1, lst = os.path.join(td, "ocr.ps1"), os.path.join(td, "list.txt")
        with open(ps1, "w", encoding="utf-8-sig") as f:   # 5.1 은 BOM 없는 ps1 을 ANSI 로 읽는다
            f.write(_OCR_PS)
        with open(lst, "w", encoding="utf-8") as f:
            f.write("\n".join(pngs) + "\n")
        try:
            r = subprocess.run([_PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, lst],
                               capture_output=True, timeout=30 + 10 * len(pngs))
        except subprocess.TimeoutExpired:
            return None, "OCR 시간 초과"
    out = r.stdout.decode("utf-8", "replace").lstrip("\ufeff").splitlines()
    if not out or not out[0].startswith("READY"):
        why = (out[0] if out else r.stderr.decode("utf-8", "replace").strip()[:200]) or f"종료 코드 {r.returncode}"
        return None, f"OCR 엔진 없음: {why}"
    OCR_ENGINE = "Windows.Media.Ocr " + out[0].split(" ", 1)[1].strip()
    res = []
    for ln in out[1:1 + len(pngs)]:
        try:
            o = json.loads(ln)
        except ValueError:
            res.append(None)
            continue
        lines = o.get("lines") if o.get("ok") else None
        if isinstance(lines, str):                         # 5.1 ConvertTo-Json = 원소 1개 배열을 스칼라로
            lines = [lines]
        res.append(None if lines is None and not o.get("ok") else [x for x in (lines or []) if x and x.strip()])
    res += [None] * (len(pngs) - len(res))
    return res, None


def ocr_cached(sha, keys, render):
    """keys(쪽 번호 등) 의 OCR 줄. 캐시(sha256 별 json)에 없는 것만 render(key, png경로) 로 그려 읽는다.

    돌려줌 = ({key: 줄 목록 | None}, 실패 까닭 | None, 엔진 이름 | None).
    """
    import tempfile
    cp = os.path.join(OCR_CACHE, f"{sha}.json")
    cache, engine = {}, None
    if os.path.isfile(cp):
        try:
            with open(cp, encoding="utf-8") as f:
                c = json.load(f)
            if c.get("dpi") == OCR_DPI:
                cache, engine = c.get("pages") or {}, c.get("engine")
        except (OSError, ValueError):
            cache = {}
    todo = [k for k in keys if str(k) not in cache]
    why = None
    if todo:
        with tempfile.TemporaryDirectory(prefix="ingest-png-") as td:
            pngs = []
            for k in todo:
                p = os.path.join(td, f"{k}.png")
                render(k, p)
                pngs.append(p)
            got, why = ocr_images(pngs)
        if got is not None:
            engine = OCR_ENGINE
            for k, lines in zip(todo, got):
                if lines is not None:                      # 장 하나의 실패는 캐시하지 않는다(다음에 다시)
                    cache[str(k)] = lines
            os.makedirs(OCR_CACHE, exist_ok=True)
            with open(cp, "w", encoding="utf-8") as f:
                json.dump({"engine": engine, "dpi": OCR_DPI, "pages": cache}, f, ensure_ascii=False)
    return {k: cache.get(str(k)) for k in keys}, why, engine


def fit(img):
    """OCR 에 넣을 그림 — 투명 배경은 흰색으로, 엔진 상한을 넘으면 줄인다."""
    from PIL import Image
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > OCR_MAX:
        s = OCR_MAX / max(img.size)
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))))
    return img


OCR_TAG = "_(OCR — 원본 글자가 아니라 그림에서 읽은 글자)_"


# ───────── 그림 소화(키워드·손글씨) — 결과는 ingest_vision 캐시에서 읽기만. 부르기는 --vision 일 때만(Claude 사용량이 든다) ─────────
def vision_entries(sha):
    """원본 sha256 의 그림 읽기 결과 {쪽 문자열|"0": 항목}. 없으면 빈 dict"""
    p = os.path.join(VAULT, "3_시스템", "_index", "ingest-vision", f"{sha}.json")
    if not os.path.isfile(p):
        return {}, ""
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        pages = d.get("pages") or {}
        model = next((e.get("model") for e in pages.values() if e.get("model")), "")
        return pages, model
    except (OSError, ValueError):
        return {}, ""


def vision_block(entry):
    import ingest_vision
    return ingest_vision.block(entry)


def pdf_empty_pages(path):
    """글자 층이 20자 미만인 쪽(= OCR·그림 읽기 대상). ex_pdf 와 같은 잣대"""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(path)
    try:
        out = []
        for i in range(len(pdf)):
            pg = pdf[i]
            tp = pg.get_textpage()
            if len(re.sub(r"\s", "", clean_plain(tp.get_text_range()))) < 20:
                out.append(i + 1)
            tp.close()
            pg.close()
        return out
    finally:
        pdf.close()


# ───────── 형식별 추출기 — (본문, 메타, 품질) ─────────
def ex_pdf(path, origin, sha):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(path)
    texts, empty = [], []
    try:
        n = len(pdf)
        for i in range(n):
            page = pdf[i]
            tp = page.get_textpage()
            s = clean_plain(tp.get_text_range())
            tp.close()
            page.close()
            if len(re.sub(r"\s", "", s)) < 20:
                empty.append(i + 1)
            texts.append(s)
        got, why, engine = {}, None, None
        if empty:
            def render(k, out):
                pg = pdf[k - 1]
                w, h = pg.get_size()
                scale = min(OCR_DPI / 72, OCR_MAX / max(w, h))
                fit(pg.render(scale=scale).to_pil()).save(out)
                pg.close()
            got, why, engine = ocr_cached(sha, empty, render)
    finally:
        pdf.close()
    vis, vmodel = vision_entries(sha)
    parts, ocred, blank = [], [], []
    for i, s in enumerate(texts, 1):
        head = "## " + link(origin, f"p.{i}", f"#page={i}")
        o = got.get(i)
        part = None
        if i in empty and o is not None:
            t = clean_plain("\n".join(o))
            if len(re.sub(r"\s", "", t)) > len(re.sub(r"\s", "", s)):   # 글자 층보다 많이 읽었을 때만 바꾼다
                part = f"{head}\n\n{OCR_TAG}\n\n{t}"
                ocred.append(i)
            else:
                blank.append(i)
        if part is None:
            part = f"{head}\n\n{s}" if s else f"{head}\n\n_(글자 없음 — 그림 쪽)_"
        if str(i) in vis:                                   # 그림 읽기(키워드·손글씨)는 쪽 아래에 덧붙인다
            part += "\n\n" + vision_block(vis[str(i)])
        parts.append(part)
    pend = [p for p in empty if p not in ocred and p not in blank]     # OCR 을 못 돌린 쪽
    pages = lambda ps: ", ".join(f"p.{p}" for p in ps)
    segs = []
    if pend:
        segs.append(f"부분 — 글자 없는 쪽 {len(pend)}/{n} (OCR 대기 · {why or '읽기 실패'}): {pages(pend)}")
    if ocred:
        segs.append(f"OCR {len(ocred)}/{n}쪽: {pages(ocred)}")
    if blank:                                           # 표지·사진 쪽 = 더 찾을 글자가 없다 — 경고 아님
        segs.append(f"OCR 로도 더 없는 쪽: {pages(blank)}")
    seen = [p for p in range(1, n + 1) if str(p) in vis]
    if seen:
        segs.append(f"그림 읽기 {len(seen)}쪽")
    q = " · ".join(segs) if pend else " · ".join(["ok"] + segs)
    ext = f"{VERSION} · pypdfium2" + (f" + {engine}" if ocred else "") + (f" + {vmodel}" if seen else "")
    return "\n\n".join(parts), {"pages": n, "extractor": ext}, q


def ex_image(path, origin, sha):
    from PIL import Image

    def render(_, out):
        with Image.open(path) as im:
            im.seek(0)                                      # gif·여러 장 tiff = 첫 장
            fit(im).save(out)
    got, why, engine = ocr_cached(sha, [0], render)
    lines = got[0]
    head = "## " + link(origin, "그림")
    vis, vmodel = vision_entries(sha)
    v = ("\n\n" + vision_block(vis["0"])) if "0" in vis else ""
    vx = f" + {vmodel}" if v else ""
    vq = " · 그림 읽기" if v else ""
    if lines is None:
        return (f"{head}{v}" if v else ""), {"extractor": VERSION + vx}, f"OCR 대기 · {why or '읽기 실패'}{vq}"
    if not lines:
        if v:   # OCR 은 없어도 그림 읽기가 있으면 찾을 거리가 있다
            return f"{head}{v}", {"extractor": f"{VERSION} + {engine}{vx}"}, "ok · OCR 글자 없음" + vq
        return f"{head}\n\n_(OCR 로도 글자 없음)_", {"extractor": f"{VERSION} + {engine}"}, "부분 — OCR 로도 글자 없음"
    return (f"{head}\n\n{OCR_TAG}\n\n" + clean_plain("\n".join(lines)) + v,
            {"extractor": f"{VERSION} + {engine}{vx}", "lines": len(lines)}, "ok · OCR" + vq)


_MD = None


def ex_markitdown(path, origin, ext):
    global _MD
    import markitdown
    if _MD is None:
        _MD = markitdown.MarkItDown(enable_plugins=False)
    t = _MD.convert(path).text_content or ""
    if ext == ".pptx":
        t = re.sub(r"<!--\s*Slide number:\s*(\d+)\s*-->", lambda m: f"## 슬라이드 {m.group(1)}", t)
    t = clean_md(t)
    if ext in (".xlsx", ".xls", ".csv"):
        t = cap_tables(t)
    ver = getattr(markitdown, "__version__", "?")
    return t, {"extractor": f"{VERSION} · markitdown {ver}"}, ("ok" if t.strip() else "글자 없음")


def ex_text(path, origin, ext):
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "cp949", "latin-1"):
        try:
            t = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lines = CTRL.sub("", t.replace("\r\n", "\n").replace("\r", "\n")).split("\n")
    note = ""
    if len(lines) > TEXT_LINES:
        note = f"\n\n> ({len(lines) - TEXT_LINES}줄 생략 — 원본 참조)"
        lines = lines[:TEXT_LINES]
    body = "\n".join(lines)
    fence = "````" if "```" in body else "```"
    return f"{fence}\n{body}\n{fence}{note}", {"lines": len(lines), "extractor": f"{VERSION} · text {enc}"}, "ok"


def _hwp_para(rec):
    """HWPTAG_PARA_TEXT → 글자. 제어 문자: 0·10·13·24~31 = 1글자, 그 밖(1~9·11·12·14~23) = 8글자(16바이트)."""
    out, buf, j, n = [], bytearray(), 0, len(rec) // 2
    while j < n:
        c = rec[2 * j] | (rec[2 * j + 1] << 8)
        if c >= 32:
            buf += rec[2 * j:2 * j + 2]
            j += 1
            continue
        if buf:
            out.append(buf.decode("utf-16-le", "replace"))
            buf = bytearray()
        if c in (0, 10, 13) or 24 <= c <= 31:
            if c == 10:
                out.append("\n")
            j += 1
        else:
            if c == 9:
                out.append("\t")
            j += 8
    if buf:
        out.append(buf.decode("utf-16-le", "replace"))
    return "".join(out)


def ex_hwp(path, origin, ext):
    paras = []
    if ext == ".hwpx":
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(path) as z:
            secs = sorted((n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)),
                          key=lambda n: int(re.findall(r"\d+", n)[-1]))
            for s in secs:
                stack = []
                for ev, el in ET.iterparse(z.open(s), events=("start", "end")):
                    tag = el.tag.rsplit("}", 1)[-1]
                    if ev == "start" and tag == "p":
                        stack.append([])
                    elif ev == "end" and tag == "t" and stack:
                        piece = el.text or ""
                        for ch in el:
                            ct = ch.tag.rsplit("}", 1)[-1]
                            piece += "\t" if ct == "tab" else "\n" if ct == "lineBreak" else ""
                            piece += ch.tail or ""
                        stack[-1].append(piece)
                    elif ev == "end" and tag == "p" and stack:
                        paras.append("".join(stack.pop()))
                        el.clear()
        ex = "hwpx xml"
    else:
        import olefile
        ole = olefile.OleFileIO(path)
        try:
            hdr = ole.openstream("FileHeader").read()
            props = int.from_bytes(hdr[36:40], "little")
            if props & 2:
                return "", {"extractor": f"{VERSION} · hwp5"}, "암호 문서 — 추출 불가"
            if props & 4:
                return "", {"extractor": f"{VERSION} · hwp5"}, "배포용 문서 — 본문 암호화로 추출 불가"
            secs = sorted((e for e in ole.listdir() if len(e) == 2 and e[0] == "BodyText" and e[1].startswith("Section")),
                          key=lambda e: int(e[1][7:]))
            for e in secs:
                data = ole.openstream(e).read()
                if props & 1:
                    data = zlib.decompress(data, -15)
                i, n = 0, len(data)
                while i + 4 <= n:
                    h = int.from_bytes(data[i:i + 4], "little")
                    i += 4
                    tag, size = h & 0x3FF, (h >> 20) & 0xFFF
                    if size == 0xFFF:
                        size = int.from_bytes(data[i:i + 4], "little")
                        i += 4
                    if tag == 67:                      # HWPTAG_PARA_TEXT
                        paras.append(_hwp_para(data[i:i + size]))
                    i += size
        finally:
            ole.close()
        ex = "hwp5 olefile"
    t = clean_plain("\n\n".join(p for p in paras if p.strip()))
    return t, {"extractor": f"{VERSION} · {ex}"}, ("ok" if t else "글자 없음")


def extract(path, origin, sha):
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF:
        return "pdf", ex_pdf(path, origin, sha)
    if ext in MARKITDOWN:
        return ext[1:], ex_markitdown(path, origin, ext)
    if ext in HWP:
        return ext[1:], ex_hwp(path, origin, ext)
    if ext in TEXT:
        return ext[1:], ex_text(path, origin, ext)
    if ext in IMAGE and ext != ".svg":
        return ext[1:], ex_image(path, origin, sha)
    if ext in MEDIA:                                    # 영상·소리 전사는 아직 없다(색인만 자리 표시)
        return ext[1:], ("", {"extractor": VERSION}, "전사 대기")
    return (ext[1:] or "?"), ("", {"extractor": VERSION}, "형식 미지원")


# ───────── 스캔·묶음 ─────────
def candidates():
    for dp, dns, fns in os.walk(SRC):
        dns[:] = sorted(d for d in dns if not d.startswith(".") and os.path.join(dp, d) != OUT)
        for fn in sorted(fns):
            if fn.startswith((".", "~$")) or fn.lower().endswith(".md"):
                continue
            yield os.path.join(dp, fn)


def existing_indexes():
    by_sha, by_origin = {}, {}
    for dp, _, fns in os.walk(OUT):
        for fn in fns:
            if fn.endswith(SUFFIX):
                p = os.path.join(dp, fn)
                fm = read_fm(p)
                if fm and fm.get("sha256"):
                    by_sha.setdefault(fm["sha256"], []).append((p, fm))
                    by_origin[fm.get("origin")] = fm
                    for a in fm.get("also") or []:
                        by_origin[a] = fm
    return by_sha, by_origin


def canonical_key(origin):
    return (origin.startswith("1_수집/_inbox/"), origin)   # 분류된 자리를 먼저


def memo_of(origin):
    stem = os.path.splitext(origin)[0]
    p = os.path.join(VAULT, *stem.split("/")) + ".md"
    return rel(p) if os.path.isfile(p) else None


def build(sha, origins, sizes, mtimes, old_fm):
    origin = origins[0]
    path = os.path.join(VAULT, *origin.split("/"))
    t0 = time.time()
    try:
        fmt, (body, meta, q) = extract(path, origin, sha)
    except Exception as e:                              # 파일 하나의 실패가 전체를 멈추지 않게
        fmt, body, meta, q = os.path.splitext(path)[1][1:], "", {"extractor": VERSION}, f"추출 실패: {type(e).__name__}: {e}"
    name = os.path.basename(origin)
    today = date.today().isoformat()
    fm = {
        "type": "semantic",
        "title": f"{name} 색인",
        "created": (old_fm or {}).get("created") or today,
        "updated": today,
        "tags": ["색인"],
        "source": "user",
        "format": fmt,
        "origin": origin,
        "also": origins[1:] or None,
        "sha256": sha,
        "size": sizes[origin],
        "mtime": mtimes[origin],
        "pages": meta.get("pages"),
        "lines": meta.get("lines"),
        "extractor": meta["extractor"],
        "quality": q,
        "confidence": "hypothesized",
        "status": "active",
    }
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + f"\n\n> ({len(body) - MAX_CHARS:,}자 생략 — 원본 참조)"
        fm["quality"] = q = f"잘림 — {MAX_CHARS:,}자 상한" + q[2:] if q.startswith("ok") else q + f" · 잘림 {MAX_CHARS:,}자"
    memo = memo_of(origin)
    head = f"> [!info] 자동 생성 색인 — 원본 {link(origin, name)}"
    if memo:
        head += f" · 메모 {link(memo, '메모')}"
    head += "\n> 찾기용입니다. 고쳐도 다시 만들 때 사라집니다."
    if origins[1:]:
        head += "\n> 같은 파일(sha256 동일): " + " · ".join(f"`{o}`" for o in origins[1:])
    # 제목 줄 = search.py gist(첫 머리글). 없으면 검색 결과 요약이 «p.1» 링크가 된다(10-14 실측).
    text = dump_fm(fm) + f"\n# {neutralize(name)} — 색인\n\n" + head + "\n\n" + (body if body else f"_({q})_") + "\n"
    return text, fmt, q, time.time() - t0


def vision_pass(groups, only, sizes, mtimes, workers):
    """그림 쪽(글자 층 20자 미만)·그림 파일 중 아직 안 읽었거나 낡은 것을 Claude 로 읽고, 그 색인만 다시 만든다.
    그림은 먼저 이 스레드에서 다 그린다(pdfium 은 스레드 안전하지 않다) → claude -p 를 workers 개씩 동시에."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import ingest_vision as V
    from PIL import Image
    import pypdfium2 as pdfium
    prof = V.profile()
    jobs = []                                                   # (sha, 쪽|0, origin, png)
    for sha, origins in sorted(groups.items(), key=lambda kv: min(kv[1], key=canonical_key)):
        origins = sorted(origins, key=canonical_key)
        if only is not None and not any(o == x or o.startswith(x.rstrip("/") + "/") for x in only for o in origins):
            continue
        origin = origins[0]
        path = os.path.join(VAULT, *origin.split("/"))
        ext = os.path.splitext(path)[1].lower()
        pages = V.load(sha)["pages"]
        try:
            if ext in PDF:
                keys = [k for k in pdf_empty_pages(path) if V.stale(pages.get(str(k)), prof[2])]
                if keys:
                    pdf = pdfium.PdfDocument(path)
                    try:
                        for k in keys:
                            pg = pdf[k - 1]
                            w, h = pg.get_size()
                            jobs.append((sha, k, origin, V.png_for_claude(fit(pg.render(scale=V.MAX_SIDE / max(w, h)).to_pil()))))
                            pg.close()
                    finally:
                        pdf.close()
            elif ext in IMAGE and ext != ".svg" and V.stale(pages.get("0"), prof[2]):
                with Image.open(path) as im:
                    im.seek(0)
                    jobs.append((sha, 0, origin, V.png_for_claude(fit(im))))
        except Exception as e:                                  # 원본 하나의 실패가 전체를 멈추지 않게
            print(f"그림 읽기 준비 실패: {origin} — {type(e).__name__}: {e}")
    if not jobs:
        print("그림 읽기: 새로 읽을 것 없음")
        return
    print(f"그림 읽기 {len(jobs)}장 · {V.MODEL} · 동시 {workers} · 글씨체 사전 {prof[2] or '없음'}")
    lock, caches, tot = threading.Lock(), {}, {"in": 0, "out": 0, "ok": 0, "fail": 0}
    today = date.today().isoformat()

    def run(job):
        sha, k, origin, png = job
        t0 = time.time()
        res, usage, err = V.call(png, f"{origin}" + (f" p.{k}" if k else ""), prof)
        return job, res, usage, err, time.time() - t0

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for fut in as_completed([ex.submit(run, j) for j in jobs]):
            (sha, k, origin, _), res, usage, err, dt = fut.result()
            where = origin + (f" p.{k}" if k else "")
            if usage.get("rate_limit"):
                print(f"  ⚠ 사용률 알림: {usage['rate_limit']}")
            if err:
                tot["fail"] += 1
                print(f"  실패 {where} — {err}")
                continue
            u = usage.get("usage") or {}
            tin = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            tot["in"] += tin
            tot["out"] += u.get("output_tokens", 0)
            tot["ok"] += 1
            res.update(model=V.MODEL, profile=prof[2], at=today, tokens={"in": tin, "out": u.get("output_tokens", 0)})
            with lock:
                c = caches.setdefault(sha, V.load(sha))
                c["pages"][str(k)] = res
                V.save(sha, c)                                  # 한 장씩 저장 — 중간에 끊겨도 다음에 이어 읽는다
            hw = f" · 손글씨 {len(res['handwriting'])}자" if res["handwriting"] else ""
            print(f"  {where} [{res['kind']} · 키워드 {len(res['keywords'])}{hw} · {tin}+{u.get('output_tokens', 0)}tok · {dt:.0f}s]")
    print(f"그림 읽기 끝: 성공 {tot['ok']} · 실패 {tot['fail']} · 토큰 입력 {tot['in']:,} + 출력 {tot['out']:,}")
    for sha in caches:                                          # 읽은 원본의 색인만 다시 만든다
        origins = sorted(groups[sha], key=canonical_key)
        target = index_path(origins[0])
        text, fmt, q, _ = build(sha, origins, sizes, mtimes, read_fm(target) if os.path.isfile(target) else None)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"색인 갱신(그림 읽기) {origins[0]}  [{q}]")


def main():
    ap = argparse.ArgumentParser(description="1_수집 원본 색인 생성")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--vision", action="store_true", help="그림 쪽·그림 파일을 Claude 로 읽는다(키워드·손글씨 · 사용량이 든다)")
    ap.add_argument("--vision-workers", type=int, default=3, help="동시에 부르는 claude -p 수")
    a = ap.parse_args()

    only = None
    if a.paths:
        only = set()
        for p in a.paths:
            ap_ = os.path.abspath(p)
            if not ap_.startswith(SRC + os.sep):
                sys.exit(f"1_수집 밖은 색인하지 않는다: {p}")
            only.add(rel(ap_))

    by_sha, by_origin = existing_indexes()
    groups, sizes, mtimes, hashed = {}, {}, {}, 0
    for p in candidates():
        r = rel(p)
        st = os.stat(p)
        sizes[r], mtimes[r] = st.st_size, int(st.st_mtime)
        old = by_origin.get(r)
        if old and old.get("size") == st.st_size and old.get("mtime") == int(st.st_mtime) and old.get("origin") == r:
            h = old["sha256"]                          # 크기·시각 같으면 해시 재사용
        else:
            h = sha256(p)
            hashed += 1
        groups.setdefault(h, []).append(r)

    stats = {"새로": 0, "갱신": 0, "옮김": 0, "같음": 0}
    warn, big, dup = [], [], []
    for sha, origins in sorted(groups.items(), key=lambda kv: min(kv[1], key=canonical_key)):
        origins.sort(key=canonical_key)
        if len(origins) > 1:
            dup.append(origins)
        for o in origins:
            if sizes[o] > BIG:
                big.append((o, sizes[o]))
        if only is not None and not any(o == x or o.startswith(x.rstrip("/") + "/") for x in only for o in origins):
            continue
        target = index_path(origins[0])
        olds = by_sha.get(sha, [])
        old_p, old_fm = olds[0] if olds else (None, None)
        same = (old_fm is not None and old_p == target and old_fm.get("extractor", "").startswith(VERSION)
                and old_fm.get("origin") == origins[0] and (old_fm.get("also") or []) == origins[1:])
        if same and not a.force:
            stats["같음"] += 1
            if not str(old_fm.get("quality")).startswith("ok"):   # «ok · OCR …» 는 경고 아님
                warn.append((origins[0], old_fm.get("quality")))
            continue
        kind = "새로" if old_fm is None else ("옮김" if old_p != target else "갱신")
        if a.dry:
            print(f"[dry] {kind} {origins[0]}")
            stats[kind] += 1
            continue
        text, fmt, q, dt = build(sha, origins, sizes, mtimes, old_fm)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        for p, _ in olds:                                   # 옮겨진 원본 = 옛 자리 색인 정리
            if p != target and os.path.exists(p):
                os.remove(p)
        stats[kind] += 1
        if not q.startswith("ok"):
            warn.append((origins[0], q))
        print(f"{kind} {origins[0]}  [{fmt} · {q} · {dt:.1f}s]")

    if a.vision and not a.dry:
        vision_pass(groups, only, sizes, mtimes, a.vision_workers)

    orphans = [p for sha, lst in by_sha.items() if sha not in groups for p, _ in lst]
    if only is None and orphans:
        for p in orphans:
            if a.prune and not a.dry:
                os.remove(p)
        print(("지운 고아 " if a.prune and not a.dry else "고아(원본 없음) ") + f"{len(orphans)}: " + " · ".join(rel(p) for p in orphans))
    if not a.dry:                                            # 빈 폴더 정리(옮김·고아 뒤)
        for dp, dns, fns in os.walk(OUT, topdown=False):
            if dp != OUT and not os.listdir(dp):
                os.rmdir(dp)

    print("== " + " · ".join(f"{k} {v}" for k, v in stats.items()) + f" · 해시 계산 {hashed}")
    for o, q in warn:
        print(f"품질: {o} — {q}")
    for g in dup:
        print("같은 파일(색인 하나): " + "  ==  ".join(g))
    for o, s in big:
        print(f"50MB 초과(git 제외 대상): {o} ({s / 1048576:.0f}MB)")


if __name__ == "__main__":
    main()
