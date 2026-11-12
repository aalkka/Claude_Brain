"""md 표 깨짐 검사·고치기 — 옵시디언에서 표가 깨지는 원인을 찾아 줄 단위로 보고한다.

사용:
  py -3 3_시스템/mdtable.py check [경로...]        # 기본 = 볼트 전체(.obsidian·.git·_색인 제외) · 원인별 개수 + 예
  py -3 3_시스템/mdtable.py check --all            # _색인 포함
  py -3 3_시스템/mdtable.py fix <파일·폴더...> [--dry]  # 고칠 수 있는 원인만 그 자리에서 고침
  py -3 3_시스템/mdtable.py hook                   # PostToolUse(Write|Edit) 훅 — 방금 쓴 md 를 고침(.claude/settings.json)

원인(2026-11-01 격리 옵시디언 1.14.5 실측 — 읽기 화면 / 실시간 미리 보기):
  no-blank   표 바로 윗줄이 글·목록(빈 줄 아님) → 두 화면 모두 표를 안 그리고 | 글자로 둠   (fix: 빈 줄 넣기)
             제목(#) 바로 아래는 표로 그림 → 문제 아님
  pipe-link  [[노트|별칭]]·![[그림|300]] 의 | → 읽기는 정상 · 실시간에서 칸이 하나 더 생김  (fix: \\| )
  pipe-code  `a|b` 코드 안 |   → 읽기는 정상 · 실시간에서 칸이 쪼개짐                 (fix: \\| — 코드 안에 \\ 가 보임)
  pipe-math  $|x|$ 수식 안 |    → 읽기는 정상 · 실시간에서 칸이 쪼개짐                 (fix: \\vert )
  cols       칸 수가 머리 줄과 다름(위 원인 아닌 것)
             넘침 → 옵시디언이 넘친 칸을 버려 내용이 사라짐  (fix: 글 속 |Δ| 막기 · 남는 칸은 마지막 칸에 « · » 로)
             모자람 → 옵시디언이 빈 칸으로 채움(머리와 어긋났으면 손으로)                 (보고만)
  html-open  코드 밖 글의 꺾쇠 `<id>`·`<run>` 이 같은 이름으로 안 닫힘(2026-11-12 격리 옵시디언 1.15.0 실측)
             → 실시간 미리 보기가 그 자리부터 HTML 로 읽어 노트 끝까지 표·제목·목록을 안 그림(빈 줄로도 안 끊김)
             · 읽기 화면은 표 정상 · <id> 글자만 사라짐 · 표 칸 안이면 그 칸의 다음 | 에서 끊김(글자만 사라짐)
             (fix: 자리표시 꼴 — = 없고 서식 태그 이름 아님 — 을 코드 칸 `<id>` 로 · 일부러 쓴 HTML 꼴은 보고만)
fix 는 1_수집/(원본 층)·3_시스템/_index/(기계 파생물)을 건드리지 않는다.
"""
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".claude"}
SEP_RE = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")


def is_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") or (s.count("|") >= 1 and SEP_RE.match(s) is not None)


def protected_spans(line: str):
    """[[..]] · `..` · $..$ 구간 [(시작, 끝, 종류)] — 그 안의 | 는 글쓴이가 칸 나누기로 쓴 것이 아니다"""
    spans = []
    for m in re.finditer(r"!?\[\[[^\]]*\]\]", line):
        spans.append((m.start(), m.end(), "link"))
    for m in re.finditer(r"(`+)(.+?)\1", line):
        spans.append((m.start(), m.end(), "code"))
    for m in re.finditer(r"(?<![\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\d)", line):
        spans.append((m.start(), m.end(), "math"))
    return spans


def raw_pipes(line: str):
    """GFM 이 칸 나누기로 보는 | 자리(역슬래시로 막지 않은 것)"""
    out = []
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c == "|":
            out.append(i)
        i += 1
    return out


def cells(line: str, pipes) -> int:
    s = line.strip()
    n = len(pipes) + 1
    if s.startswith("|"):
        n -= 1
    if s.endswith("|") and not s.endswith("\\|"):
        n -= 1
    return n


def in_code_fence(lines):
    """줄마다 코드 울타리 안인가"""
    inside = False
    out = []
    for l in lines:
        if re.match(r"^\s*(```|~~~)", l):
            out.append(True)
            inside = not inside
            continue
        out.append(inside)
    return out


def scan(text: str, html: bool = True):
    """표마다 문제 [(줄 번호, 원인, 줄 글)] · html=True 면 꺾쇠(html-open)도 줄마다 한 번"""
    lines = text.split("\n")
    fence = in_code_fence(lines)
    probs = []
    i = 0
    # 앞머리(프론트매터)는 건너뜀
    if lines and lines[0].strip() == "---":
        for k in range(1, len(lines)):
            if lines[k].strip() == "---":
                i = k + 1
                break
    while i < len(lines) - 1:
        if fence[i] or not is_row(lines[i]) or not SEP_RE.match(lines[i + 1].strip()) or fence[i + 1]:
            i += 1
            continue
        head = i
        j = i + 2
        while j < len(lines) and not fence[j] and lines[j].strip() and "|" in lines[j]:
            j += 1
        prev = lines[head - 1] if head > 0 else ""
        if head > 0 and prev.strip() and not re.match(r"^\s*(>|#{1,6}\s|(---|___|\*\*\*)\s*$)", prev):
            # 머리 줄 바로 위가 글·목록 → 옵시디언이 읽기·실시간 미리 보기 모두 표 대신 글자로 둔다(11-01 실측 · 제목 바로 아래는 표로 그림)
            probs.append((head + 1, "no-blank", prev))
        want = cells(lines[head + 1], raw_pipes(lines[head + 1]))
        for k in range(head, j):
            if k == head + 1:
                continue
            l = lines[k]
            ps = raw_pipes(l)
            spans = protected_spans(l)
            bad = {}
            for p in ps:
                for a, b, kind in spans:
                    if a < p < b:
                        bad[kind] = bad.get(kind, 0) + 1
                        break
            for kind in bad:
                probs.append((k + 1, "pipe-" + kind, l))
            if not bad and cells(l, ps) != want:
                probs.append((k + 1, "cols", l))
        i = j
    seen = set()
    for ln, a, b, _, _ in html_open(text) if html else []:
        if ln not in seen:
            seen.add(ln)
            probs.append((ln, "html-open", lines[ln - 1][max(0, a - 40):b + 30]))
    return probs


# ── 꺾쇠 태그(html-open) ─────────────────────────────────────
# 11-12 격리 옵시디언 1.15.0 실측 + 앱 안 lib/codemirror/markdown.js(CM5 markdown 모드 · app.js 의 hypermd 가 감쌈)를 읽음:
# 실시간 미리 보기는 코드 밖 글에서 `<태그` 를 만나면 HTML 모드로 들어가고, 열린 태그가 모두 닫혀야(문맥이 비어야) 마크다운으로
# 돌아온다. 빈 줄로도 안 끊긴다 → `<id>` 하나가 그 아래 표·제목·목록을 노트 끝까지 글자로 둔다. 표 줄 안이면 다음 | 에서 끊긴다.
# 닫는 태그는 이름이 달라도 가장 안쪽 하나를 닫는다(CM5 xml) — 그래서 «같은 이름으로 닫힘»만 정상으로 친다.
_S = r"[\t\n\x0b\x0c\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]"  # JS \s
HTML_TRIG = re.compile(r"<(?:!--|\?|!\[CDATA\[|([a-z][a-z0-9-]*)(?:%s+[a-z_:.\-]+(?:%s*=%s*[^>]+)?)*%s*(?:>|$))" % (_S, _S, _S, _S), re.I | re.A)
_AUTO = re.compile(r"<(?:https?|ftps?)://(?:[^\\>]|\\.)+>")
_MAIL = re.compile(r"<[^> \\]+@(?:[^\\>]|\\.)+>")
_MDIN = re.compile(r"markdown\s*=\s*('|\"){0,1}1('|\"){0,1}")
_WIKI = re.compile(r"!?\[\[(.*?)\]\]")
_FOOT = re.compile(r"\[\^[^\]\s]*?\]")
_HREF = {"(": re.compile(r"\((?:[^\\()]|\\.|\((?:[^\\()]|\\.)*\))*?\)"), "[": re.compile(r"\[(?:[^\\\[\]]|\\.|\[(?:[^\\\[\]]|\\.)*\])*?\]")}
_ESC = set("\\`*{}[]()#+,-.!_>~|\"$%&',/:;<=?@^")
_FENCE = re.compile(r"^ ?(~~~+|```+)[ \t]*([\w/+#-]*)[^\n`]*$")  # CM5 fencedCodeRE
_LIST = re.compile(r"^(?:[*\-+]|[0-9]+[.)])\s+(?:\[.\]\s+)?")
_HEAD = re.compile(r"^ {0,3}#{1,6}(?: |$)")
_QUOTE = re.compile(r"^(?: {0,3}>[ \t]?)+")
_WORD = re.compile(r"[^\s\u00a0=<>\"']*[^\s\u00a0=<>\"'/]")
VOID = set("area base br col command embed frame hr img input keygen link meta param source track wbr menuitem".split())
IMPLICIT = set("dd li optgroup option p rp rt tbody td tfoot th tr".split())
_PBLOCK = set("address article aside blockquote dir div dl fieldset footer form h1 h2 h3 h4 h5 h6 header hgroup hr menu nav ol p pre section table ul".split())
GRAB = {"dd": {"dd", "dt"}, "dt": {"dd", "dt"}, "li": {"li"}, "option": {"option", "optgroup"}, "optgroup": {"optgroup"}, "p": _PBLOCK,
        "rp": {"rp", "rt"}, "rt": {"rp", "rt"}, "tbody": {"tbody", "tfoot"}, "td": {"td", "th"}, "tfoot": {"tbody"}, "th": {"td", "th"},
        "thead": {"tbody", "tfoot"}, "tr": {"tr"}}
# 일부러 쓰는 HTML 이름 — 안 닫혀도 코드 칸으로 바꾸지 않고 알리기만(읽기 화면에선 그 꼴대로 그려져 글쓴이 뜻일 수 있다)
HTML_KEEP = set("a abbr address article aside audio b bdi bdo big blockquote button canvas caption center cite code colgroup dd del details "
                "dfn dialog div dl dt em fieldset figcaption figure font footer form h1 h2 h3 h4 h5 h6 header i iframe ins kbd label legend li "
                "main mark marquee math nav nobr noscript object ol optgroup option p picture pre q rp rt ruby s samp section select small span "
                "strike strong sub summary sup svg table tbody td textarea tfoot th thead tr tt u ul var video".split())


def _indent(s: str) -> int:
    n = 0
    for ch in s:
        if ch == " ":
            n += 1
        elif ch == "\t":
            n += 4  # CM5: 탭 = 4칸
        else:
            break
    return n


def table_rows(lines) -> set:
    """표에 든 줄 번호(0부터) — scan 과 같은 판정"""
    fence = in_code_fence(lines)
    rows = set()
    i = 0
    while i < len(lines) - 1:
        if fence[i] or not is_row(lines[i]) or not SEP_RE.match(lines[i + 1].strip()) or fence[i + 1]:
            i += 1
            continue
        j = i + 2
        while j < len(lines) and not fence[j] and lines[j].strip() and "|" in lines[j]:
            j += 1
        rows.update(range(i, j))
        i = j
    return rows


_SPEC = re.compile(r"[`\\$\[!\]<]")
_MSPEC = re.compile(r"[\\$|]")


def _next_trigger(raw: str, i: int, st: dict, quote: bool, intable: bool):
    """raw[i:] 를 마크다운 글로 훑어 첫 HTML 시작 (자리, 일치) · 없으면 None. st(code·math)는 줄을 넘어 이어진다.
    코드 칸·수식·위키링크·각주·링크 주소·자동 링크·\\< 안은 HTML 로 안 읽힌다(옵시디언 hypermd 순서대로)."""
    n = len(raw)
    while i < n:
        if st["code"]:  # 코드 칸 — 같은 길이 ` 줄에서 닫힘
            i = raw.find("`", i)
            if i < 0:
                return None
            j = i
            while j < n and raw[j] == "`":
                j += 1
            if j - i == st["code"]:
                st["code"] = 0
            i = j
            continue
        if st["math"]:  # 수식 — 같은 $·$$ 에서 닫힘 · 표 줄은 | 에서도
            m = _MSPEC.search(raw, i)
            if not m:
                return None
            i = m.start()
            if raw[i] == "\\":
                i += 2
            elif raw.startswith(st["math"], i):
                i += len(st["math"])
                st["math"] = None
            else:
                if raw[i] == "|" and intable:
                    st["math"] = None
                i += 1
            continue
        m = _SPEC.search(raw, i)  # 이 밖의 글자는 HTML·코드·수식을 열지 않는다
        if not m:
            return None
        i = m.start()
        c = raw[i]
        if c == "`":
            j = i
            while j < n and raw[j] == "`":
                j += 1
            if not quote or j - i == 1:  # CM5: 인용 안에서는 ` 하나만 코드 칸을 연다
                st["code"] = j - i
            i = j
            continue
        if c == "\\":
            i += 2 if i + 1 < n and raw[i + 1] in _ESC else 1
            continue
        if c == "$":
            if raw.startswith("$$", i):
                st["math"] = "$$"
                i += 2
                continue
            if i + 1 < n and not raw[i + 1].isspace() and raw[i + 1] != "$":
                h = re.search(r"[^\\]\$(.|$)", raw[i + 1:])
                if h and re.match(r"[^\s\\]\$([^0-9]|$)", h.group(0)):
                    st["math"] = "$"
            i += 1
            continue
        if c in "[!":
            m = _WIKI.match(raw, i) or _FOOT.match(raw, i)
            if m:
                i = m.end()
                continue
        if c == "]" and i + 1 < n and raw[i + 1] in _HREF:
            m = _HREF[raw[i + 1]].match(raw, i + 1)
            if m:
                i = m.end()
                continue
        if c == "<":
            m = _AUTO.match(raw, i) or _MAIL.match(raw, i)
            if m:
                i = m.end()
                continue
            m = HTML_TRIG.match(raw, i)
            if m:
                return i, m
        i += 1
    return None


def html_region(text: str, start: int, table: bool = False):
    """text[start] 의 HTML 시작부터 옵시디언 HTML 모드를 흉내 낸다(CM5 xml·htmlmixed). (끝 자리, 판정)
    판정: ok = 빈 요소·주석 닫힘·같은 이름으로 닫힘·HTML 규칙의 저절로 닫힘 · other = 다른 이름의 닫는 태그에 우연히 끝남
          eof = 끝까지 안 닫힘 · cut = 표 줄의 다음 | 에서 잘림"""
    n = len(text)
    ctx = []
    i = start
    while i < n:
        c = text[i]
        if c == "<":
            popped = None
            ends = {"<!--": "-->", "<![CDATA[": "]]>", "<?": "?>"}
            head = next((h for h in ends if text.startswith(h, i)), None)
            if head:
                j = text.find(ends[head], i + len(head))
                if j < 0:
                    return n, "eof"
                i = j + len(ends[head])
            elif text.startswith("<!", i):
                i += 2
            else:
                close = text.startswith("</", i)
                j = i + (2 if close else 1)
                name, end = None, None
                while j < n:
                    ch = text[j]
                    if ch.isspace():
                        j += 1
                    elif ch == ">":
                        end, j = "end", j + 1
                        break
                    elif text.startswith("/>", j):
                        end, j = "self", j + 2
                        break
                    elif ch == "=":
                        j += 1
                    elif ch == "<":
                        end = "bad"  # CM5: 태그 안 < = 그 태그를 버리고 < 부터 다시
                        break
                    elif ch in "\"'":
                        k = text.find(ch, j + 1)
                        if k < 0:
                            return n, "eof"
                        j = k + 1
                    else:
                        m = _WORD.match(text, j + 1)
                        k = m.end() if m else j + 1
                        if name is None:
                            name = text[j:k]
                        j = k
                if end is None:
                    return n, "eof"
                i = j
                if end == "bad":
                    continue
                low = (name or "").lower()
                if close and name:
                    if ctx and ctx[-1] != low and ctx[-1] in IMPLICIT:
                        ctx.pop()
                        popped = "ok"
                    if ctx:
                        popped = "ok" if ctx.pop() == low else "other"
                elif name:
                    while ctx and ctx[-1] in GRAB and low in GRAB[ctx[-1]]:
                        ctx.pop()
                        popped = "ok"
                    if end != "self" and low not in VOID:
                        ctx.append(low)
                        if low in ("script", "style"):  # htmlmixed: 닫는 태그까지 CSS·JS
                            m = re.compile(r"</s*%ss*>" % low, re.I).search(text, i)
                            if not m:
                                return n, "eof"
                            i = m.start()
            if not ctx:
                return i, popped or "ok"
        elif table and c == "|" and text[i - 1] != "\\":
            return i, "cut"
        else:
            j = text.find("<", i + 1)
            if table:
                k = text.find("|", i + 1)
                if k >= 0 and (j < 0 or k < j):
                    j = k
            i = j if j >= 0 else n
    return n, "eof"


def html_open(text: str):
    """[(줄, 시작 칸, 끝 칸, 태그 글, 고칠 수 있나)] — 코드 밖 글의 HTML 시작 중 같은 이름으로 안 닫히는 것.
    고칠 수 있나 = 자리표시 꼴(태그가 그 줄에서 > 로 끝남 · = 없음 · HTML_KEEP 이름 아님) → 코드 칸으로 감싼다.
    코드 판정이 애매하면 코드로 친다(울타리 닫힘은 같은 들여쓰기만 · 4칸 들여쓰기는 목록 안이어도 코드) — 코드 안을 고치지 않으려고."""
    lines = text.split("\n")
    raws = [l[:-1] if l.endswith("\r") else l for l in lines]
    offs, o = [], 0
    for l in lines:
        offs.append(o)
        o += len(l) + 1
    k0 = 0
    if raws and raws[0].lstrip("\ufeff").strip() == "---":  # 앞머리(속성) — 안 닫히면 노트 전체가 앞머리(옵시디언도 그렇게 읽음)
        for k in range(1, len(raws)):
            if raws[k].startswith("---") and not raws[k][3:].strip():
                k0 = k + 1
                break
        else:
            return []
    rows = table_rows(lines)
    st = {"code": 0, "math": None}
    fence = None  # (글자, 길이, 닫는 줄 들여쓰기 아래, 위)
    prev = "blank"  # 앞줄 꼴 — 4칸 들여쓴 코드 판정(CM5: 빈 줄·코드·제목·울타리 끝 뒤)
    hend = -1  # 정상으로 닫힌 HTML 구역의 끝(절대 자리)
    out = []
    for k in range(k0, len(raws)):
        raw, a = raws[k], offs[k]
        if hend >= a + len(raw):  # 줄 전체가 HTML 구역 안
            prev = "other" if raw.strip() else "blank"
            continue
        col = hend - a if hend > a else 0
        if st["code"] in (1, 2):  # hypermd: 줄이 바뀌면 `·`` 코드 칸은 끝남
            st["code"] = 0
        qm = _QUOTE.match(raw)
        quote = bool(qm and qm.group(0))
        if col == 0:
            if not raw.strip():
                prev = "blank"
                continue
            ind = _indent(raw)
            if fence:
                m = re.match(r"(\s*)(`+|~+) *$", raw)
                if m and m.group(2)[0] == fence[0] and len(m.group(2)) >= fence[1] and fence[2] <= _indent(m.group(1)) <= fence[3]:
                    fence, prev = None, "fenceend"
                else:
                    prev = "other"
                continue
            body = raw.lstrip()
            lm = _LIST.match(body)
            fm = _FENCE.match(body[lm.end():] if lm else body)
            if fm:  # 여는 줄은 넓게(들여쓰기 무관) — 코드로 더 치는 쪽
                fence = (fm.group(1)[0], len(fm.group(1)), ind, ind + (4 if lm else 0))
                st["code"], prev = 0, "other"
                continue
            if ind >= 4 and prev in ("blank", "code", "header", "fenceend"):
                prev = "code"
                continue
            if quote and _FENCE.match(raw[qm.end():].lstrip()):  # CM5: 인용 속 울타리는 코드 칸(3)을 켜고 끈다
                st["code"] = 0 if st["code"] == 3 else 3
                prev = "other"
                continue
            prev = "header" if _HEAD.match(raw) else "other"
        else:
            prev = "other"
        intable = k in rows
        pos = col
        while True:
            t = _next_trigger(raw, pos, st, quote, intable)
            if not t:
                break
            ti, m = t
            gt = raw.find(">", ti)
            if m.group(1) and gt >= 0 and _MDIN.search(raw, ti, gt):
                stop, verdict = a + gt + 1, "ok"  # markdown="1" — > 뒤에서 바로 마크다운으로
            else:
                stop, verdict = html_region(text, a + ti, intable)
            if verdict == "ok":
                hend = stop
                if stop <= a + len(raw):
                    pos = stop - a
                    continue
                break
            tag = m.group(0)
            ok = bool(m.group(1)) and tag.endswith(">") and "=" not in tag and m.group(1).lower() not in HTML_KEEP
            out.append((k + 1, ti, ti + len(tag), tag, ok))
            pos = ti + len(tag)  # 고쳤다고 치고 그 뒤를 계속 본다(뒤의 다른 꺾쇠도 찾게)
    return out


def wrap_tags(text: str, left: list | None = None):
    """html-open 중 자리표시 꼴을 코드 칸 `<id>` 으로 감싼다(11-12 실측: 코드 칸·&lt;·같은 이름 닫기 = 정상).
    표 칸 안이어도 | 를 더하지 않아 칸이 안 쪼개진다. 일부러 쓴 HTML 꼴은 고치지 않고 줄 번호를 left 에."""
    found = html_open(text)
    if not found:
        return text, 0
    lines = text.split("\n")
    spans = {}
    for ln, a, b, _, ok in found:
        if ok:
            spans.setdefault(ln - 1, []).append((a, b))
        elif left is not None:
            left.append(ln)
    n = 0
    for k, ss in spans.items():
        l = lines[k]
        for a, b in sorted(ss, reverse=True):
            pre = " " if a > 0 and l[a - 1] == "`" else ""  # 옆 ` 와 붙으면 `` 가 되어 코드 칸 짝이 바뀐다
            post = " " if b < len(l) and l[b] == "`" else ""
            l = l[:a] + pre + "`" + l[a:b] + "`" + post + l[b:]
            n += 1
        lines[k] = l
    return "\n".join(lines), n


def header_cells(lines, k: int) -> int:
    """k 줄이 속한 표의 머리 칸 수(구분 줄 기준)"""
    while k > 0 and not SEP_RE.match(lines[k].strip()):
        k -= 1
    return cells(lines[k], raw_pipes(lines[k]))


def fix_cols(l: str, want: int) -> str:
    """머리보다 칸이 많은 줄 — ①글 속 절댓값 |Δ| 의 | 를 막고 ②그래도 넘치는 칸은 마지막 칸에 « · » 로 붙인다
    (옵시디언은 넘치는 칸을 버려 그 내용이 화면에서 사라진다 — 덧붙인 내용이 새 칸으로 들어간 줄)"""
    l = re.sub(r"(?<=\s)\|([^\s|]{1,8})\|(?=\s)", r"\\|\1\\|", l)
    ps = raw_pipes(l)
    if cells(l, ps) <= want:
        return l
    s = l.rstrip()
    lead = 1 if s.lstrip().startswith("|") else 0
    inner = ps[lead:]  # 칸 사이 | 들(맨 끝 | 포함일 수 있음)
    # want 번째 칸 뒤의 칸 나누기들을 « · » 로
    cut = inner[want - 1 :]
    if s.endswith("|"):
        cut = cut[:-1]
    out = l
    for p in reversed(cut):
        out = out[:p].rstrip() + " · " + out[p + 1 :].lstrip()
    out = re.sub(r"·\s+·", "·", out)  # 붙인 칸이 « · » 로 시작했으면 겹친 점 하나로
    return out


def fix_text(text: str, merge: bool = True, left: list | None = None, wrap: bool = True):
    """merge=False(훅) — 넘친 칸 합치기는 하지 않고 그 줄 번호를 left 에 담는다: 넘친 | 가 줄 끝 덧붙임인지
    칸 가운데 실수인지 기계가 가를 수 없다(11-01 실측: 가운데 | 를 끝 칸에 합쳐 «30곳» 이 옆 칸으로 밀림)
    wrap=True 면 먼저 꺾쇠 자리표시를 코드 칸으로(wrap_tags) — 칸 위치를 바꾸지 않는다(| 를 안 더함)"""
    text, changed = wrap_tags(text) if wrap else (text, 0)
    lines = text.split("\n")
    probs = scan(text, html=False)
    blank_before = set()
    for ln, kind, _ in probs:
        k = ln - 1
        l = lines[k]
        if kind == "no-blank":
            blank_before.add(k)
            continue
        if kind == "cols":
            want = header_cells(lines, k)
            if cells(l, raw_pipes(l)) > want:
                if not merge:
                    if left is not None:
                        left.append(ln)
                    continue
                nl = fix_cols(l, want)
                if nl != l:
                    lines[k] = nl
                    changed += 1
            continue
        if kind not in ("pipe-link", "pipe-code", "pipe-math"):
            continue
        spans = [s for s in protected_spans(l) if "pipe-" + s[2] == kind]
        out = []
        last = 0
        for a, b, sk in sorted(spans):
            seg = l[a:b]
            if sk == "math":
                new = re.sub(r"(?<!\\)\|", r"\\vert ", seg)
            else:
                new = re.sub(r"(?<!\\)\|", r"\\|", seg)
            out.append(l[last:a] + new)
            last = b
        out.append(l[last:])
        nl = "".join(out)
        if nl != l:
            lines[k] = nl
            changed += 1
    for k in sorted(blank_before, reverse=True):
        lines.insert(k, "\r" if lines[k - 1].endswith("\r") else "")  # CRLF 파일은 CRLF 빈 줄
        changed += 1
    return "\n".join(lines), changed


def files(args, include_index: bool):
    roots = [Path(a) for a in args] or [VAULT]
    for r in roots:
        r = r if r.is_absolute() else VAULT / r
        if r.is_file():
            yield r
            continue
        for p in r.rglob("*.md"):
            rel = p.relative_to(VAULT).parts
            if any(d in SKIP_DIRS for d in rel):
                continue
            if not include_index and rel[:2] == ("1_수집", "_색인"):
                continue
            yield p


def fixable(p: Path) -> bool:
    try:
        rel = p.resolve().relative_to(VAULT).parts
    except ValueError:
        return False
    return p.suffix == ".md" and rel[:1] != ("1_수집",) and rel[:2] != ("3_시스템", "_index") and not any(d in SKIP_DIRS for d in rel)


def limit_msgs(p: Path) -> list:
    """상시로 읽히는 파일(기억 색인·MOC·recent·open-loops·CLAUDE.md)이 상한을 넘으면 쓰는 순간 알린다.
    드물게 점검해서는 808자 줄·188k MOC 가 될 때까지 몰랐다(11-02). 훅을 새로 달지 않으려고 여기서 함께 잰다."""
    if p.suffix != ".md":
        return []
    try:
        import drift
        return [f"상한: {w} — {t}. 줄여라(이력은 본문으로)." for _, w, t in drift.limits_of(str(p))][:5]
    except Exception:
        return []


def hook() -> int:
    """PostToolUse(Write|Edit) — 방금 쓴 md 의 표를 그 자리에서 고친다(Claude 가 «설명:» 바로 아래 표를 쓰는 버릇의 재발 막기).
    고쳤으면 Claude 에게 알린다(다시 Edit 하려면 Read 먼저). 실패해도 도구 결과를 막지 않는다."""
    import json

    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
        fp = (data.get("tool_input") or {}).get("file_path") or ""
        p = Path(fp)
        if not fp or not p.is_file():
            return 0
        msg = limit_msgs(p)
        if fixable(p):
            t = p.read_text(encoding="utf-8")
            left: list = []
            hl: list = []
            nt, w = wrap_tags(t, hl)
            nt, n = fix_text(nt, merge=False, left=left, wrap=False)
            if w or n:
                p.write_text(nt, encoding="utf-8", newline="")
                if w:
                    msg.append(f"mdtable: {p.name} 의 코드 밖 꺾쇠 자리표시 {w}곳을 코드 칸 `<…>` 으로 감쌌다(옵시디언 실시간 미리 보기가 HTML 태그로 읽어 그 아래 표·제목을 안 그림).")
                msg.append((f"mdtable: {p.name} 의 md 표 {n}곳을 고쳤다(표 위 빈 줄 · 칸 안 | 막기). " if n else "") + "이 파일을 다시 Edit 하려면 먼저 Read.")
            # 보고만 할 꺾쇠 — 표 위 빈 줄을 넣었으면 줄 번호가 밀려 고친 글에서 다시 잰다
            bad = sorted({h[0] for h in html_open(nt) if not h[4]}) if hl and n else sorted(set(hl))
            if bad:
                msg.append(f"mdtable: {p.name} 줄 {', '.join(map(str, bad[:8]))} 의 꺾쇠 태그가 같은 이름으로 안 닫힌다 — 옵시디언 실시간 미리 보기는 "
                           f"그 아래를 노트 끝까지 마크다운으로 안 그린다. 일부러 쓴 HTML 이면 닫고, 아니면 코드 칸 `<…>` 으로.")
            if left:
                # 고친 뒤 줄 번호(빈 줄을 넣었으면 밀림) — 고친 글에서 다시 잰다
                left2: list = []
                fix_text(nt, merge=False, left=left2)
                msg.append(f"mdtable: {p.name} 줄 {', '.join(map(str, left2 or left))} 이 머리보다 칸이 많다 — 옵시디언은 넘친 칸을 버린다. 글 속 | 는 \\| 로 막거나 칸을 합쳐라.")
        if not msg:
            return 0
        msg = " ".join(msg)
        sys.stdout.buffer.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}, ensure_ascii=False).encode("utf-8"))
    except Exception:
        pass
    return 0


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["hook"]:
        return hook()
    if not argv or argv[0] not in ("check", "fix"):
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    include_index = "--all" in rest
    dry = "--dry" in rest
    paths = [a for a in rest if not a.startswith("--")]
    if cmd == "check":
        total = {}
        nfiles = 0
        ntables = 0
        examples = {}
        for p in files(paths, include_index):
            try:
                t = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            ntables += sum(1 for l in t.split("\n") if SEP_RE.match(l.strip()) and "-" in l)
            pr = scan(t)
            if not pr:
                continue
            nfiles += 1
            for ln, kind, l in pr:
                total[kind] = total.get(kind, 0) + 1
                examples.setdefault(kind, []).append(f"{p.relative_to(VAULT)}:{ln}  {l.strip()[:110]}")
        print(f"표 {ntables}개 · 문제 있는 파일 {nfiles}개")
        for kind, n in sorted(total.items(), key=lambda x: -x[1]):
            print(f"  {kind}: {n}")
            for e in examples[kind][:4]:
                print(f"     {e}")
        return 0
    if not paths:
        print("fix 는 파일을 적어야 합니다")
        return 2
    for p in files(paths, True):
        if not fixable(p):
            continue
        t = p.read_text(encoding="utf-8")
        nt, n = fix_text(t)
        if n:
            print(f"{'(미리 보기) ' if dry else ''}{p.relative_to(VAULT)}: {n}곳")
            if not dry:
                p.write_text(nt, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
