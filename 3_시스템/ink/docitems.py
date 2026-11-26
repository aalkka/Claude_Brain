"""문제지 문항 표(11-22 · 사용자 «더 보는 게 쪽 단위가 아니라 더 필요한 부분까지만» · look «문항 2.1 15» 를 받침).
  py -3 docitems.py <문서.pdf> [--json] [--sheet <폴더>]
  → {"doc", "pages", "items": [{"id": "2.1-15", "sec": "2.1", "num": "15", "page": 7, "y0": pt, "y1": pt, "h": 쪽 높이 pt, "head": 첫 줄 ≤60자, "src": "text|ocr"}], "ocr_pages": [...]}
y 는 PDF 쪽 위에서 잰 pt(72dpi) · y0 = 문항 머리 줄 위 · y1 = 다음 문항 머리 위(같은 쪽) 또는 쪽 글의 끝.
쪽마다: 글층에 본문이 있으면 글자 상자로 줄을 만들고 · 없으면(스캔·그림 쪽) 윈도우 내장 OCR(Windows.Media.Ocr · ingest.py 와 같은 엔진)로 줄과 상자를 받는다.
문항 머리 = 줄 첫머리 «15.» «15)» «Problem 15» «문제 15» «15번» · 단원 = 쪽 머리의 «(2.1)»·«2.1절»·«Section 2.1» (없으면 빈칸 · 앞 쪽 단원을 이어 씀).
--sheet = 문항마다 잘라 낸 그림을 한 장씩(검사용).
  py -3 docitems.py <문서.pdf> --no-wait → 캐시 표 또는 {"pending": true}(즉시 · 없으면 뒤에서 만들기를 띄움 · 만드는 중이면 안 띄움)
  py -3 docitems.py <폴더> --warm → 그 아래 과제·숙제·시험·문제 PDF 표를 미리(있으면 건너뜀)
  py -3 docitems.py <노트.note> --bg K → {"bg": 바탕 PDF(볼트 상대) | null, "page": 그 PDF 쪽(1부터) | null} · K = 노트의 보이는 쪽 차례(1부터)
쓰는 곳 = 노트 곁창 실행기(brain-base notedoc · 문제지 짝 · look «문항 X» → page N y0-y1)."""
import json, os, re, subprocess, sys, tempfile

VAULT = os.environ.get("BRAIN_VAULT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # <볼트>/3_시스템/ink/docitems.py → 그 볼트(대역 서버 사본 볼트면 그 사본 캐시)
SCALE = 300 / 72          # OCR 그림 = 300dpi
OCR_PX = 4000             # 그림 긴 변 상한(윈도우 OCR 한도 10000 · 사진 PDF 쪽은 3000pt 넘음)
FOOT = 0.94              # 이보다 아래에서 시작하는 줄 = 꼬리말(11-22 0.9 → Review 1.33 (f) 줄이 잘림)
BODY_MIN = 60             # 글층 글자가 이보다 적으면 그림 쪽으로 봄(머리·쪽 번호만 있는 슬라이드)
HEAD = re.compile(r"^\s*\*?\s*(?:(?:Problem|Prob\.?|Exercise|Q|문제)\s*(\d{1,3}(?:\.\d{1,3})?)|(\d{1,2}\.\d{1,3})(?=\s+\S)|(\d{1,3})\s*(?:[.)]|번)(?=\s|$|[A-Za-z가-힣(]))", re.I)  # 15. · 1.33(복습 쪽 «단원.번호») · Problem 15
SEC = re.compile(r"(?:\((\d{1,2}\.\d{1,2})\)|Section\s+(\d{1,2}\.\d{1,2})|(\d{1,2}\.\d{1,2})\s*절|\(([A-Za-z가-힣]{3,})\))", re.I)  # 쪽 머리 «(2.1)» · «(Review)»

_PS = r'''
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
$engine = $null
foreach ($tag in @("en-US", "ko")) { if ($engine -eq $null) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new($tag)) } }
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
    $ls = @(@($res.Lines) | ForEach-Object {
      $ws = @($_.Words); $x0 = 1e9; $y0 = 1e9; $x1 = 0; $y1 = 0
      foreach ($w in $ws) { $r = $w.BoundingRect; if ($r.X -lt $x0) { $x0 = $r.X }; if ($r.Y -lt $y0) { $y0 = $r.Y }; if ($r.X + $r.Width -gt $x1) { $x1 = $r.X + $r.Width }; if ($r.Y + $r.Height -gt $y1) { $y1 = $r.Y + $r.Height } }
      [ordered]@{ t = $_.Text; b = @([int]$x0, [int]$y0, [int]$x1, [int]$y1) } })
    $o = [ordered]@{ ok = $true; lines = $ls }
    $bmp.Dispose(); $stream.Dispose()
  } catch { $o = [ordered]@{ ok = $false; err = $_.Exception.Message } }
  [Console]::Out.WriteLine((ConvertTo-Json $o -Compress -Depth 5))
}
'''
_PSEXE = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")


def ocr(pngs):
    """PNG 목록 → 장마다 [(글, (x0,y0,x1,y1) px)] · 실패 = None."""
    with tempfile.TemporaryDirectory(prefix="docitems-") as td:
        ps1, lst = os.path.join(td, "ocr.ps1"), os.path.join(td, "list.txt")
        open(ps1, "w", encoding="utf-8-sig").write(_PS)
        open(lst, "w", encoding="utf-8").write("\n".join(pngs) + "\n")
        r = subprocess.run([_PSEXE, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, lst], capture_output=True,
                           timeout=60 + 15 * len(pngs), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out = r.stdout.decode("utf-8", "replace").lstrip("\ufeff").splitlines()
    if not out or not out[0].startswith("READY"):
        raise RuntimeError("OCR 엔진 없음: " + (out[0] if out else r.stderr.decode("utf-8", "replace")[:200]))
    res = []
    for ln in out[1:1 + len(pngs)]:
        try:
            o = json.loads(ln)
        except ValueError:
            res.append(None); continue
        ls = o.get("lines") if o.get("ok") else None
        if isinstance(ls, dict):
            ls = [ls]
        res.append(None if ls is None else [(l["t"], tuple(l["b"])) for l in ls if l.get("t")])
    return res + [None] * (len(pngs) - len(res)), out[0].split(" ", 1)[1]


def text_lines(pg):
    """글층 → [(글, (x0,y0,x1,y1) pt · 위에서 잼)] — 글자 상자를 줄로 묶음."""
    tp = pg.get_textpage(); n = tp.count_chars(); H = pg.get_size()[1]
    chars = []
    for i in range(n):
        c = tp.get_text_range(i, 1)
        if not c.strip():
            chars.append((c, None)); continue
        l, b, r, t = tp.get_charbox(i)
        chars.append((c, (l, H - t, r, H - b)))
    lines, cur, box = [], "", None
    for c, bx in chars + [("\n", None)]:
        if c in "\r\n":
            if cur.strip() and box:
                lines.append((cur.strip(), box))
            cur, box = "", None; continue
        cur += c
        if bx:
            box = bx if not box else (min(box[0], bx[0]), min(box[1], bx[1]), max(box[2], bx[2]), max(box[3], bx[3]))
    return lines


CACHE = os.path.join(VAULT, "3_시스템", "_index", "docitems")  # git 밖(_index) · 임시 폴더는 윈도우가 비울 수 있어 볼트 안에
LOCK_S = 600  # 만드는 중 표시가 이보다 오래면 죽은 것으로 봄


def _ck(doc):
    import hashlib
    p = doc if os.path.isabs(doc) else os.path.join(VAULT, doc)
    st = os.stat(p)
    key = f"{os.path.relpath(p, VAULT)}|{st.st_mtime_ns}|{st.st_size}|{FOOT}|{OCR_PX}|v4|{HEAD.pattern}|{SEC.pattern}"
    return p, os.path.join(CACHE, hashlib.sha256(key.encode()).hexdigest()[:16] + ".json")


def items(doc, sheet=None):
    """캐시 = 3_시스템/_index/docitems/<경로·mtime·크기 해시>.json(OCR 한 번 30초/20쪽 → 다음은 즉시)."""
    p, ck = _ck(doc)
    if not sheet and os.path.exists(ck):
        return json.load(open(ck, encoding="utf-8"))
    r = _items(doc, p, sheet)
    os.makedirs(CACHE, exist_ok=True)
    tmp = ck + f".{os.getpid()}.tmp"
    json.dump(r, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, ck)  # 반쯤 쓴 표를 다른 쪽이 읽지 않게
    return r


def cached_or_start(doc):
    """기다리지 않기(첫 질문 · 칸이 열릴 때) — 캐시가 있으면 표 · 없으면 뒤에서 만들기를 띄우고 {"pending": true}(이미 만드는 중이면 다시 안 띄움)."""
    p, ck = _ck(doc)
    if os.path.exists(ck):
        return json.load(open(ck, encoding="utf-8"))
    lock = ck + ".lock"
    import time
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < LOCK_S:
        return {"doc": doc, "pending": True, "why": "만드는 중"}
    os.makedirs(CACHE, exist_ok=True)
    open(lock, "w").write(str(os.getpid()))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([sys.executable, os.path.abspath(__file__), doc, "--build", "--lock", lock], cwd=VAULT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    return {"doc": doc, "pending": True, "why": "뒤에서 만들기 시작"}


def warm(root, pat=r"과제|숙제|시험|문제|problem|homework|assignment|exam|quiz"):
    """폴더 아래 문제지 같은 PDF(이름·폴더가 pat)의 표를 미리 — 이미 있으면 건너뜀 · 예약·ingest 뒤에 부르는 길."""
    done, made = 0, 0
    for dp, _, fs in os.walk(os.path.join(VAULT, root) if not os.path.isabs(root) else root):
        for f in fs:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, VAULT).replace(os.sep, "/")
            if not f.lower().endswith(".pdf") or not re.search(pat, rel, re.I):
                continue
            if os.path.exists(_ck(rel)[1]):
                done += 1
                continue
            try:
                items(rel); made += 1
            except Exception as e:  # noqa: BLE001
                print(f"  실패 {rel}: {e}", file=sys.stderr)
    return {"warm": root, "had": done, "made": made}


def _items(doc, p, sheet=None):
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(p)
    per, need = {}, []
    td = tempfile.mkdtemp(prefix="docitems-png-")
    for i in range(len(d)):
        pg = d[i]
        tl = text_lines(pg)
        body = sum(len(t) for t, _ in tl)
        if body >= BODY_MIN and any(HEAD.match(t) for t, _ in tl):
            per[i] = (tl, "text")
        else:
            png = os.path.join(td, f"p{i + 1}.png")
            sc = min(SCALE, OCR_PX / max(pg.get_size()))  # 큰 쪽(사진 PDF 3000pt)은 OCR 한도 안으로
            pg.render(scale=sc).to_pil().save(png)
            need.append((i, png, sc))
    eng = None
    if need:
        res, eng = ocr([png for _, png, _ in need])
        for (i, _, sc), ls in zip(need, res):
            per[i] = ([(t, tuple(v / sc for v in b)) for t, b in (ls or [])], "ocr")
    out, sec = [], ""
    for i in range(len(d)):
        W, H = d[i].get_size()
        ls, src = per.get(i, ([], "none"))
        ls = sorted(ls, key=lambda x: (x[1][1], x[1][0]))
        top = [t for t, b in ls if b[1] < H * 0.2]
        m = next((SEC.search(t) for t in top if SEC.search(t)), None)
        if m:
            sec = next(g for g in m.groups() if g)
        # 문항 머리: 줄 첫머리 번호 + 왼쪽 여백 가까이(본문 안 «2.» 같은 것은 빼려고 · 쪽 너비 40% 안)
        heads = []
        for t, b in ls:
            mm = HEAD.match(t)
            if mm and b[0] < W * 0.4 and b[1] > H * 0.08:
                heads.append((next(g for g in mm.groups() if g), t, b))
        end = max([b[3] for t, b in ls if b[1] <= H * FOOT] or [H])  # 꼬리말(쪽 번호·이름) = 맨 아래 띠
        # 쪽 머리 덩이(첫 문항 머리 위 · 앞 쪽에서 이어진 글이나 OCR 이 놓친 첫 문항) — 두 줄 이상이고 쪽 높이 6% 넘을 때만(슬라이드 제목 한 줄은 뺌)
        first = heads[0][2][1] if heads else end
        pre = [b for t, b in ls if H * 0.03 < b[1] < first - 2 and b[1] <= H * FOOT and not SEC.search(t)]
        if len(pre) >= 2 and first - min(b[1] for b in pre) > H * 0.06:
            out.append({"id": f"p{i + 1}-앞", "sec": sec, "num": None, "page": i + 1, "y0": round(max(0, min(b[1] for b in pre) - 4), 1),
                        "y1": round(first - 4, 1), "h": round(H, 1), "head": "(쪽 머리 — 앞에서 이어진 글 또는 못 찾은 문항)", "src": src})
        for k, (num, t, b) in enumerate(heads):
            y0 = max(0, b[1] - 4)
            y1 = heads[k + 1][2][1] - 4 if k + 1 < len(heads) else min(H, end + 6)
            y1 = max(y1, b[3] + 4)  # 머리 줄이 꼬리말 띠에 걸린 마지막 문항(«60.» y1 < y0) — 적어도 머리 줄은 담음
            out.append({"id": f"{sec}-{num}" if sec else num, "sec": sec, "num": num, "page": i + 1, "y0": round(y0, 1), "y1": round(y1, 1),
                        "h": round(H, 1), "head": t[:60], "src": src})
    if sheet:
        os.makedirs(sheet, exist_ok=True)
        for it in out:
            im = d[it["page"] - 1].render(scale=2).to_pil()
            im.crop((0, int(it["y0"] * 2), im.width, int(it["y1"] * 2))).save(os.path.join(sheet, f"{it['page']:02d}-{it['id'].replace('/', '_')}.png"))
    return {"doc": doc, "pages": len(d), "items": out, "ocr_pages": [n[0] + 1 for n in need], "ocr": eng}


def bg_of(note, k):
    """보이는 쪽 차례 k → 바탕 PDF 쪽(inkrender.load_note 와 같은 차례 셈 · page·after·po·pdel)."""
    head, pages = None, []
    with open((note if os.path.isabs(note) else os.path.join(VAULT, note)), encoding="utf-8") as f:
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
                    pg = {"page": r["page"], "bg": r.get("bg")}
                    at = next((i for i, p in enumerate(pages) if p["page"] == r.get("after")), -1)
                    pages.insert(at + 1, pg) if at >= 0 else pages.append(pg)
            elif isinstance(r.get("po"), list):
                by = {p["page"]: p for p in pages}
                hd = [by[i] for i in map(str, r["po"]) if i in by]
                pages = hd + [p for p in pages if p not in hd]
            elif isinstance(r.get("pdel"), str):
                pages = [p for p in pages if p["page"] != r["pdel"]]
    bg = (head or {}).get("bg")
    path = bg.get("path") if isinstance(bg, dict) else None
    if not path or not 1 <= k <= len(pages) or not isinstance(pages[k - 1].get("bg"), int):
        return {"bg": path, "page": None}
    n = pages[k - 1]["bg"] + 1
    try:  # 그 쪽 높이(look 보이는 범위가 다음 쪽으로 넘지 않게)
        import pypdfium2 as pdfium
        d = pdfium.PdfDocument(path if os.path.isabs(path) else os.path.join(VAULT, path))
        return {"bg": path, "page": n, "pages": len(d), "h": round(d[n - 1].get_size()[1], 1)}
    except Exception:  # noqa: BLE001
        return {"bg": path, "page": n}


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.stdout.reconfigure(encoding="utf-8")
    if "--bg" in a:  # 필기 쪽 → 바탕 PDF 쪽 짝
        print(json.dumps(bg_of(a[0], int(a[a.index("--bg") + 1])), ensure_ascii=False))
        sys.exit(0)
    if "--no-wait" in a:  # 첫 질문·칸 열림: 캐시 표 또는 {"pending"} 즉시
        print(json.dumps(cached_or_start(a[0]), ensure_ascii=False))
        sys.exit(0)
    if "--build" in a:  # cached_or_start 가 띄운 뒤쪽 일
        try:
            items(a[0])
        finally:
            lk = a[a.index("--lock") + 1] if "--lock" in a else None
            if lk and os.path.exists(lk):
                os.remove(lk)
        sys.exit(0)
    if "--warm" in a:  # 폴더 미리 만들기
        print(json.dumps(warm(a[0]), ensure_ascii=False))
        sys.exit(0)
    r = items(a[0], a[a.index("--sheet") + 1] if "--sheet" in a else None)
    if "--json" in a:
        print(json.dumps(r, ensure_ascii=False))
    else:
        print(f"{r['doc']} · {r['pages']}쪽 · OCR 쪽 {len(r['ocr_pages'])} ({r['ocr']})")
        for it in r["items"]:
            print(f"  {it['id']:>9} p{it['page']:<3} y {it['y0']:>6}~{it['y1']:<6} [{it['src']}] {it['head']}")
