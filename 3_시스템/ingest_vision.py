"""그림 읽기 — 그림이 무엇을 그렸는지 명사구 하나(+ 손글씨가 있으면 전사)를 Claude 로 얻는다. ingest.py --vision 이 부른다.

층: ①글자 = 윈도우 OCR(ingest.py, 무료·즉시) ②무엇을 그렸나 = 명사구 30자 안 ③손글씨 = 있을 때만 전사(claude -p · 구독 · 키 불필요).
로컬 손글씨 OCR 은 쓰지 않는다 — 제작자 볼트 실측(PaddleOCR 파인튜닝 글자 판독 45~49%).

토큰 줄이기(사용자 10-26 «색인에 드는 토큰을 획기적으로» · 형식 = 명사구 — 실제 결과를 보고 고름):
  - 그림을 SIDE(512px)로 줄여 BATCH 장씩 한 번에 묻는다 — 512 와 768 의 결과가 같았다(표본 9장).
    호출마다 붙는 고정분(claude -p 숨은 머리 약 650토큰 + 안내)을 장수로 나눈다.
  - 캐시 쓰기 끔(DISABLE_PROMPT_CACHING) — 한 번 쓰고 버리는 입력이라 1시간 캐시 쓰기(입력값 2배)만 손해(같은 묶음 34% 차이).
  - --effort low · 출력 = 명사구와 손글씨 여부만. 손글씨가 있다고 나온 그림만 원래 해상도(HW_SIDE)로 한 장씩 다시 읽어 전사한다.
  - 실측(표본 9장 · sonnet 5.5 · 명사구·문장·낱말을 다 받은 시험): 장당 입력 342 + 출력 118 · 이전(1568px · 한 장씩 · 긴 JSON) 2,690 + 440.
    haiku 5.5 는 생각 토큰(1,265)이 붙어 같은 묶음이 3배 비쌌다 → sonnet.
  - 생각 끔(--settings alwaysThinkingEnabled=false · 11-02 사용자 «글자 선택에 드는 토큰 최소화») — 옮겨 적기에 생각은 값어치가 없다.
    수식 쪽 출력 4,515 → 1,791(글 길이 같음) · MAX_THINKING_TOKENS=0 은 듣지 않았다(4,471).
  - PDF 손글씨 = 전사와 판서 위치를 한 번에(read_boxes): 번호 그림 한 장으로 덩이별 전사. 쪽당 입력 8,002 + 출력 1,383(전사 + locate) → 3,843 + 688(표본 2쪽).
    1092px 는 입력이 2,700 으로 더 줄지만 기각: 덩이 나눔이 바뀌고(4쪽 43 → 48) 전사 일치 0.91 → 0.84 · 출력이 3,249 까지 뛴다.

호출 = 볼트 밖 cwd · --setting-sources user · --no-session-persistence · --disable-slash-commands
  (볼트 훅·CLAUDE.md·세션 기록이 끼지 않게 — 훅은 볼트 .claude/settings.json 에만). 그림은 메시지에 base64 로 바로 붙인다.
  claude = 설치된 것 중 가장 새 판(claude_bin.py) · 모델 = 별칭 sonnet(10-30 사용자 «새 모델이 나와도 옛 판을 쓰지 않게»).

글씨체 사전 = 3_시스템/handwriting/profile.md + samples.json(표본 그림 → 정답) — 손글씨 전사 호출에만 붙는다.
결과 = 3_시스템/_index/ingest-vision/<sha256>.json {pages: {쪽|0|img:…: {n, handwriting, model, profile, at, tokens, pos?}}}
  pos = PDF 쪽 판서 위치 {v: 2, aspect, items: [[x1, y1, x2, y2, 낱말, 줄끝], …](쪽 비율)} — brain-source 끌어 고르기 층(11-02 ·
        ingest.py vision_pass · hwlayout.py · read_boxes = 전사와 한 번에). v 가 2 가 아니면 다음 «그림 읽기» 가 그 쪽을 다시 읽는다
"""
import base64, hashlib, io, json, os, re, subprocess, sys, tempfile, time

import claude_bin

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(VAULT, "3_시스템", "_index", "ingest-vision")
HW = os.path.join(VAULT, "3_시스템", "handwriting")
MODEL = os.environ.get("INGEST_VISION_MODEL", "sonnet")   # 별칭 — 가장 새 claude 가 지금 판으로 푼다
SIDE = 512                 # 무엇을 그렸나 — 긴 변
HW_SIDE = 1568             # 손글씨 전사 — Claude 그림 권장 긴 변(넘으면 서버가 줄인다)
BATCH = 10                 # 한 번에 묻는 그림 수
TIMEOUT = 300
SYSTEM = "JSON만 출력한다."
HW_SYSTEM = "손글씨 전사기. 전사한 글만 출력한다."    # JSON 지시와 섞으면 전사를 JSON 으로 감싸 온다(10-26 실측)

ASK = """학습 자료 그림 {n}장의 검색 색인. 그림마다 JSON 원소 하나를 순서대로 담은 배열 하나만 출력:
{{"n":"무엇을 그렸나 — 명사구 30자 안(그림에 쓰인 용어는 원문 그대로)","hw":손글씨가 있으면 true 아니면 false}}"""

HW_ASK = """이 그림의 손글씨를 쓰인 그대로 옮긴다(고치지 않는다·지어내지 않는다). 줄바꿈 유지. 수식은 글자로(예: ∮E·dA = Q/ε0, x^2, a_n).
못 읽는 글자는 [?]. 인쇄 글자는 빼고 손글씨만. 전사한 글만 출력한다(설명·코드 울타리 금지)."""

# 판서 전사 + 위치(11-02 · PDF 쪽만): 잉크 «글 덩이»에 번호를 그린 그림(hwlayout.marked) 한 장 → 번호마다 그 안의 글.
# 위치는 잉크에서 · 글은 읽는 쪽이 정한다(너비만으로 짝지으면 그림 꼬리표가 옆 문장에 붙었다). 그림 안 글씨(꼬리표)는 색인에만 남기고 덧씌우지 않는다.
BOX_SYSTEM = "번호와 글만 출력한다."
BOX_ASK = """그림의 파란 상자마다 빨간 번호가 붙어 있다. 상자마다 그 안의 손글씨를 쓰인 그대로 옮긴다(고치지 않는다·지어내지 않는다). 파란 상자·빨간 번호는 옮기지 않는다.
수식은 글자로(예: ∮E·dA = Q/ε0, x^2, a_n). 못 읽는 글자는 [?]. 한 줄에 «번호<TAB>글» 하나씩, 번호 순서대로 모두.
상자가 글줄이 아니라 그림·선·화살표면 «번호<TAB>#그림 안 글씨들»(글씨가 없으면 «번호<TAB>#»). 설명 금지."""


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


def png(img, side):
    """PIL 그림 → 긴 변 side 이하 PNG bytes"""
    if max(img.size) > side:
        s = side / max(img.size)
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _img(b):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(b).decode("ascii")}}


class Stop(Exception):
    """그림 읽기를 멈출 까닭(사용자 10-26 «구독 아닐 때 멈추고 · 사용량이 없어 못 읽으면 한도 알림»). kind = "구독 아님" | "사용량 한도" | "로그인 안 됨"
    로그인 안 됨 = 플러그인이 로그인 창을 띄우고, 창이 닫히면 다시 읽는다(사용자 11-02)."""

    def __init__(self, kind, why):
        super().__init__(f"{kind}: {why}")
        self.kind, self.why = kind, why


# 구독 확인은 한 곳(claude_bin · 11-11 구독 해지 대비) — 옛 이름은 부르는 쪽(ingest·notice-filter)을 위해 남긴다
PAID_ENV = claude_bin.PAID_ENV
NO_LOGIN = claude_bin.NO_LOGIN
LOGIN_ERR = claude_bin.LOGIN_TEXT
subscription = claude_bin.subscription


def _reset(info):
    t = info.get("resetsAt")
    return time.strftime("%m-%d %H:%M", time.localtime(t)) if isinstance(t, (int, float)) and t > 0 else "알 수 없음"


def _run(content, system=SYSTEM, cache=False):
    """claude -p 한 번 → (응답 글, 사용량 {in, out, cost, parts, rate_limit?}, 오류 글 | "").
    cache=True = 프롬프트 캐시를 켠다 — 같은 내용을 되풀이할 때만 이득. 10-29 실측: Claude Code 가 사용자 글 끝까지 캐시에 쓰고
    (쓰기 2배) 다음 호출은 앞부분만 읽어, 본문이 다른 호출을 잇달아도 손해다(공지 추출 첫 호출 $0.0096 → $0.0163). 기본 = 끔.
    구독이 아닌 길로 나갔거나(init 의 apiKeySource) 사용량 한도에 막히면 Stop 을 던진다 — 부른 쪽은 남은 그림을 묻지 않는다."""
    cmd = [claude_bin.newest(), "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
           "--model", MODEL, "--effort", "low", "--tools", "", "--system-prompt", system, "--strict-mcp-config",
           "--setting-sources", "user", "--settings", '{"alwaysThinkingEnabled":false}', "--no-session-persistence", "--disable-slash-commands"]
    payload = (json.dumps({"type": "user", "message": {"role": "user", "content": content}}, ensure_ascii=False) + "\n").encode("utf-8")
    env = dict(os.environ) if cache else dict(os.environ, DISABLE_PROMPT_CACHING="1")
    with tempfile.TemporaryDirectory(prefix="ingest-vision-") as cwd:     # 볼트 밖에서 — 볼트 훅·CLAUDE.md 가 끼지 않게
        try:
            r = subprocess.run(cmd, cwd=cwd, input=payload, capture_output=True, timeout=TIMEOUT, env=env)
        except subprocess.TimeoutExpired:
            return "", {}, f"시간 초과 {TIMEOUT}s"
    text, usage, err, source, limit, kind_err = "", {}, "", None, None, ""
    for ln in r.stdout.decode("utf-8", "replace").splitlines():
        if not ln.startswith("{"):
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            source = d.get("apiKeySource")
        elif d.get("type") == "assistant" and d.get("error"):       # CLI 가 붙인 오류 종류(authentication_failed 등 · 모델 <synthetic>)
            kind_err = str(d["error"])
        elif d.get("type") == "result":
            text = d.get("result") or ""
            u = d.get("usage") or {}
            usage.update({"in": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
                          "out": u.get("output_tokens", 0), "cost": d.get("total_cost_usd"),
                          "parts": {"new": u.get("input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0),
                                    "cache_read": u.get("cache_read_input_tokens", 0)}})
            if d.get("is_error"):
                err = str(d.get("api_error_status") or d.get("result") or "is_error")
        elif d.get("type") == "rate_limit_event":
            info = d.get("rate_limit_info") or {}
            if info.get("status") == "rejected":                # 한도에 막힘(추가 결제도 꺼져 있으면 여기서 멈춘다)
                limit = info
            elif info.get("status") != "allowed":                # 한도 가까움 등 — 알리기만
                usage["rate_limit"] = json.dumps(info or d, ensure_ascii=False)[:200]
    if source not in (None, "none"):                            # 호출 전 확인을 지나쳤어도 — 다음 그림부터는 묻지 않는다
        raise Stop("구독 아님", f"apiKeySource={source}")
    failed = bool(kind_err or err or not text)
    cut = claude_bin.note_call(not failed, kind_err or ("rate_limit" if limit is not None else ""), "\n".join([err, text, r.stderr.decode("utf-8", "replace")[-500:]]) if failed else "", err)
    if cut in (claude_bin.LAPSED, claude_bin.LOGIN):            # 해지·로그인 끊김 — 상태 파일에 적혔다(알림은 부른 쪽이 claude_bin.alert)
        raise Stop(cut, (err if err and err != "401" else text or err or kind_err)[:120])
    if limit is not None or (err and re.search(r"(?i)429|usage limit|rate.?limit|limit reached|hit your limit|한도", err)):
        info = limit or {}
        raise Stop("사용량 한도", f"{info.get('rateLimitType') or '한도'} · 다시 가능 {_reset(info)}" + ("" if limit else f" · {err[:120]}"))
    if not text and not err:
        err = (r.stderr.decode("utf-8", "replace").strip() or f"종료 코드 {r.returncode}")[:300]
    return text, usage, err


def name_batch(pngs):
    """작은 그림 여러 장 → ([{n, hw} | None …], 사용량, 오류 글). 배열 길이가 맞지 않으면 전부 실패로 본다(차례가 어긋나면 남의 이름이 붙는다)."""
    content = [{"type": "text", "text": ASK.format(n=len(pngs))}]
    for i, b in enumerate(pngs, 1):
        content += [{"type": "text", "text": f"그림 {i}"}, _img(b)]
    text, usage, err = _run(content)
    if err:
        return [None] * len(pngs), usage, err
    t = text.strip()
    try:
        arr = json.loads(t[t.index("["): t.rindex("]") + 1])
    except ValueError:
        return [None] * len(pngs), usage, "JSON 아님: " + text[:200]
    if not isinstance(arr, list) or len(arr) != len(pngs):
        return [None] * len(pngs), usage, f"그림 {len(pngs)}장에 답 {len(arr) if isinstance(arr, list) else '?'}개"
    out = []
    for x in arr:
        x = x if isinstance(x, dict) else {}
        out.append({"n": str(x.get("n") or "").strip()[:60], "hw": x.get("hw") is True})
    return out, usage, ""


def transcribe(png_hi, prof):
    """손글씨 그림 한 장(원래 해상도) → (전사 글, 사용량, 오류 글). 글씨체 사전이 있으면 앞에 붙인다."""
    text, samples, _ = prof
    content = [{"type": "text", "text": HW_ASK}]
    if text or samples:
        content.append({"type": "text", "text": "글씨체 사전(이 사람 글씨 버릇):\n" + (text or "(규칙 없음)")})
        for b, t in samples:
            content += [_img(b), {"type": "text", "text": "위 표본의 정답:\n" + t}]
    content += [{"type": "text", "text": "옮길 그림:"}, _img(png_hi)]
    out, usage, err = _run(content, HW_SYSTEM)
    t = out.strip()
    if t.startswith("```"):
        t = t.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if t.startswith("{"):                                       # 그래도 JSON 으로 감싸 오면 첫 글 값을 꺼낸다
        try:
            t = next((v for v in json.loads(t).values() if isinstance(v, str)), t).strip()
        except ValueError:
            pass
    return t, usage, err


def read_boxes(png_marked, prof, n):
    """번호 그린 쪽 그림 → (덩이 n 개마다 글 | None(그림·답 없음), 색인에 넣을 전사 전체, 사용량, 오류 글). 글씨체 사전이 있으면 앞에 붙인다."""
    text, samples, _ = prof
    content = [{"type": "text", "text": BOX_ASK}]
    if text or samples:
        content.append({"type": "text", "text": "글씨체 사전(이 사람 글씨 버릇):\n" + (text or "(규칙 없음)")})
        for b, t in samples:
            content += [_img(b), {"type": "text", "text": "위 표본의 정답:\n" + t}]
    content += [{"type": "text", "text": "그림:"}, _img(png_marked)]
    out, usage, err = _run(content, BOX_SYSTEM)
    got, lines, seen = [None] * n, [], False
    for ln in out.splitlines():
        m = re.match(r"^\s*(\d+)\s*[\t:.)]?\s*(.*?)\s*$", ln)
        if not m or not 1 <= int(m.group(1)) <= n:
            continue
        seen = True
        t = m.group(2)
        if t.startswith("#") or t == "-":                       # 그림 — 안 글씨는 색인에만
            t = t.lstrip("#-").strip()
        elif t:
            got[int(m.group(1)) - 1] = t
        if t:
            lines.append(t)
    if not err and n and not seen:
        err = "번호 답 없음: " + out[:120]
    return got, "\n".join(lines), usage, err


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


def _family(m):
    """claude-sonnet-5-5 · sonnet → sonnet (모르면 그대로)"""
    f = re.search(r"opus|sonnet|haiku|fable", str(m or ""))
    return f.group(0) if f else str(m or "")


def stale(entry, prof_ver):
    """다시 읽어야 하나: 없음 · 모델 갈래가 바뀜 · 명사구가 없는 옛 판(10-26 전 = 키워드·긴 설명) · 손글씨가 있었는데 글씨체 사전 판이 바뀜.
    갈래로 견준다 — 별칭으로 바꾼 10-30 전 결과(claude-sonnet-5-5)와 새 판이 나와도 다시 읽지 않는다(사용량이 저절로 들지 않게)."""
    if not entry or _family(entry.get("model")) != _family(MODEL) or "n" not in entry:
        return True
    return bool(entry.get("handwriting")) and entry.get("profile", "") != prof_ver


def block(entry):
    """색인 본문에 붙일 글 — 한 줄(+ 손글씨)"""
    if not entry or not (entry.get("n") or entry.get("handwriting")):
        return ""
    out = f"그림(Claude 판독): {entry.get('n') or '—'}"
    if entry.get("handwriting"):
        out += "\n\n손글씨(Claude 판독):\n" + entry["handwriting"]
    return out


if __name__ == "__main__":   # 시험: py -3 3_시스템/ingest_vision.py <그림>...
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    from PIL import Image
    t0 = time.time()
    res, usage, err = name_batch([png(Image.open(p).convert("RGB"), SIDE) for p in sys.argv[1:]])
    print(json.dumps({"sec": round(time.time() - t0, 1), "err": err, "result": res, "usage": usage}, ensure_ascii=False, indent=1))
