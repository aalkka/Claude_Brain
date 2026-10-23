"""그림 소화 — 그림 쪽·그림 파일을 Claude 가 읽어 «그림 키워드 + 손글씨(사용자 글씨체)» 를 낸다. ingest.py --vision 이 부른다.

층: ①글자 = 윈도우 OCR(ingest.py, 무료·즉시) ②그림 키워드 ③손글씨 = 이 파일(claude -p · 구독 · 키 불필요).
로컬 손글씨 OCR 은 쓰지 않는다 — 제작자 실측(PaddleOCR 파인튜닝 손글씨 판독 45~49%).

호출 = 제작자 실측 조합(호출당 원시 85,953 → 2,156토큰):
  claude -p --input-format stream-json --output-format stream-json --verbose --model M --tools "" --system-prompt 짧게 --strict-mcp-config
  + 볼트 밖에서 실행(cwd = 임시 폴더) · --setting-sources user · --no-session-persistence · --disable-slash-commands
    → 볼트 훅(SessionStart 등)·CLAUDE.md·스킬이 끼지 않고, «기록 미완료 세션» 도 생기지 않는다(훅은 볼트 .claude/settings.json 에만 있음).
그림은 메시지에 base64 로 바로 붙인다(Read 왕복 없음). 도구 0개.

글씨체 사전 = 3_시스템/handwriting/profile.md(글자 버릇·헷갈리는 쌍·기호) + samples.json(표본 그림 → 정답). 호출마다 앞에 붙고,
사전 판(profile 해시)이 바뀌면 손글씨가 있던 그림만 다시 읽는다. 사전·표본은 사용자 필기로 만든다.

결과 = 3_시스템/_index/ingest-vision/<sha256>.json {model, profile, pages: {쪽|0: {kind, keywords, handwriting, printed, uncertain, usage}}}
"""
import base64, hashlib, io, json, os, subprocess, sys, tempfile, time

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(VAULT, "3_시스템", "_index", "ingest-vision")
HW = os.path.join(VAULT, "3_시스템", "handwriting")
MODEL = os.environ.get("INGEST_VISION_MODEL", "claude-sonnet-5-5")   # 10-15: sonnet 5.5
MAX_SIDE = 1568            # Claude 그림 권장 긴 변 — 넘으면 서버가 줄인다(토큰만 늘고 정보는 같음)
TIMEOUT = 180
SYSTEM = "너는 원본 색인기다. 그림을 읽고 JSON 객체 하나만 출력한다."

RULES = """이 그림은 학습 자료(강의 슬라이드·교재·판서·필기·회로도·그래프·실험 사진)의 한 쪽이다. 검색 색인을 만든다.
JSON 객체 하나만 출력한다(코드 울타리·설명 금지):
{"kind": "슬라이드|교재|판서|필기|회로도|그래프|표|실험사진|사진|기타",
 "keywords": ["그림이 보여 주는 것 — 대상·개념·부품·장비 이름 5~12개. 그림에 쓰인 용어는 그대로(영어면 영어), 보이는 것을 부르는 말은 한국어"],
 "handwriting": "손글씨 전사. 없으면 빈 문자열",
 "printed": "인쇄 글자 중 그림 안에 있어 놓치기 쉬운 것(축 이름·부품 값·표 머리). 없으면 빈 문자열",
 "uncertain": ["확신 없는 판독 — '읽은 것 (다른 후보)' 꼴"]}
손글씨 규칙: 쓰인 그대로 옮긴다(고치지 않는다·지어내지 않는다). 줄바꿈 유지. 수식은 글자로(예: ∮E·dA = Q/ε0, x^2, a_n). 못 읽는 글자는 [?].
아래 «글씨체 사전» 이 있으면 그 사람 글씨 버릇대로 읽는다."""


def profile():
    """글씨체 사전 → (본문 글, 표본 [(그림 bytes, 정답)], 판 해시). 없으면 빈 사전."""
    text, samples = "", []
    p = os.path.join(HW, "profile.md")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            text = f.read().strip()
    s = os.path.join(HW, "samples.json")
    if os.path.isfile(s):
        with open(s, encoding="utf-8") as f:
            for it in json.load(f):
                ip = os.path.join(HW, it["image"])
                if os.path.isfile(ip):
                    with open(ip, "rb") as g:
                        samples.append((g.read(), it["text"]))
    h = hashlib.sha256(text.encode("utf-8"))
    for b, t in samples:
        h.update(hashlib.sha256(b).digest())
        h.update(t.encode("utf-8"))
    return text, samples, (h.hexdigest()[:12] if text or samples else "")


def png_for_claude(img):
    """PIL 그림 → 긴 변 MAX_SIDE 이하 PNG bytes"""
    if max(img.size) > MAX_SIDE:
        s = MAX_SIDE / max(img.size)
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _img_block(b):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(b).decode("ascii")}}


def message(png, where, prof):
    text, samples, _ = prof
    content = [{"type": "text", "text": RULES}]
    if text or samples:
        content.append({"type": "text", "text": "글씨체 사전:\n" + (text or "(규칙 없음)")})
        for b, t in samples:
            content.append(_img_block(b))
            content.append({"type": "text", "text": "위 표본의 정답:\n" + t})
    content.append({"type": "text", "text": f"색인할 그림: {where}"})
    content.append(_img_block(png))
    return {"type": "user", "message": {"role": "user", "content": content}}


def call(png, where, prof):
    """그림 한 장 → (결과 dict | None, 사용량 dict, 오류 글 | "")"""
    cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
           "--model", MODEL, "--tools", "", "--system-prompt", SYSTEM, "--strict-mcp-config",
           "--setting-sources", "user", "--no-session-persistence", "--disable-slash-commands"]
    payload = (json.dumps(message(png, where, prof), ensure_ascii=False) + "\n").encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="ingest-vision-") as cwd:     # 볼트 밖에서 — 볼트 훅·CLAUDE.md 가 끼지 않게
        try:
            r = subprocess.run(cmd, cwd=cwd, input=payload, capture_output=True, timeout=TIMEOUT)   # claude.exe(셸 불필요)
        except subprocess.TimeoutExpired:
            return None, {}, f"시간 초과 {TIMEOUT}s"
    text, usage, err, limit = "", {}, "", ""
    for ln in r.stdout.decode("utf-8", "replace").splitlines():
        if not ln.startswith("{"):
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if d.get("type") == "result":
            text = d.get("result") or ""
            usage = {"usage": d.get("usage") or {}, "modelUsage": d.get("modelUsage") or {}, "cost": d.get("total_cost_usd")}
            if d.get("is_error"):
                err = str(d.get("api_error_status") or d.get("result") or "is_error")
        elif d.get("type") == "rate_limit_event":
            info = d.get("rate_limit_info") or {}
            if info.get("status") != "allowed":                # 매 호출 오는 «허용됨» 은 알리지 않는다(10-15 실측: 9번 다 allowed)
                limit = json.dumps(info or d, ensure_ascii=False)[:200]
    if not text and not err:
        err = (r.stderr.decode("utf-8", "replace").strip() or f"종료 코드 {r.returncode}")[:300]
    if limit:
        usage["rate_limit"] = limit
    if err:
        return None, usage, err
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        res = json.loads(t[t.index("{"): t.rindex("}") + 1])
    except ValueError:
        return None, usage, "JSON 아님: " + text[:200]
    out = {
        "kind": str(res.get("kind") or ""),
        "keywords": [str(k) for k in (res.get("keywords") or []) if str(k).strip()][:15],
        "handwriting": str(res.get("handwriting") or "").strip(),
        "printed": str(res.get("printed") or "").strip(),
        "uncertain": [str(u) for u in (res.get("uncertain") or [])][:20],
    }
    return out, usage, ""


def load(sha):
    p = os.path.join(CACHE, f"{sha}.json")
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {"pages": {}}


def save(sha, data):
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, f"{sha}.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def stale(entry, prof_ver):
    """다시 읽어야 하나: 없음 · 모델이 바뀜 · 손글씨가 있었는데 글씨체 사전 판이 바뀜"""
    if not entry:
        return True
    if entry.get("model") != MODEL:
        return True
    return bool(entry.get("handwriting")) and entry.get("profile", "") != prof_ver


def block(entry):
    """색인 본문에 붙일 글(쪽 아래)"""
    if not entry:
        return ""
    lines = [f"_(그림 읽기 — {entry.get('model', MODEL)} · 기계 판독, 인용은 원본에서)_"]
    head = " · ".join(x for x in [entry.get("kind", ""), ", ".join(entry.get("keywords") or [])] if x)
    if head:
        lines.append(f"그림: {head}")
    if entry.get("printed"):
        lines.append(f"그림 속 글자: {entry['printed']}")
    if entry.get("handwriting"):
        lines.append("손글씨:\n" + entry["handwriting"])
    if entry.get("uncertain"):
        lines.append("불확실: " + " · ".join(entry["uncertain"]))
    return "\n\n".join(lines)


if __name__ == "__main__":   # 시험: py -3 3_시스템/ingest_vision.py <pdf> <쪽>  |  <그림>
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    from PIL import Image
    src = sys.argv[1]
    if src.lower().endswith(".pdf"):
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(src)
        pg = pdf[int(sys.argv[2]) - 1]
        w, h = pg.get_size()
        img = pg.render(scale=MAX_SIDE / max(w, h)).to_pil().convert("RGB")
        where = f"{os.path.basename(src)} p.{sys.argv[2]}"
    else:
        img = Image.open(src).convert("RGB")
        where = os.path.basename(src)
    png = png_for_claude(img)
    t0 = time.time()
    res, usage, err = call(png, where, profile())
    print(json.dumps({"sec": round(time.time() - t0, 1), "png_kb": len(png) // 1024, "err": err, "result": res, "usage": usage}, ensure_ascii=False, indent=1))
