"""가장 새 claude 실행 파일 + 구독 확인 — 볼트 대본이 claude -p 를 부를 때 쓴다(ingest_vision · notice-filter · server).

설치된 것 중 판이 가장 높은 것: 데스크톱 앱이 스스로 올리는 판(%LOCALAPPDATA%/Claude-Data/<id>/claude-code/<판>/<해시>/claude.exe)
· 독립 설치(~/.local/bin/claude.exe) · PATH. 없으면 "claude"(PATH 에 맡김). 시험 = 환경변수 BRAIN_CLAUDE_BIN(가짜 실행 파일).
까닭(10-30 실측): 독립 설치 2.1.287(10-02 뒤 안 올라감)은 별칭 haiku 를 Haiku 4.5 로, 데스크톱 앱 판 2.1.309 는 Haiku 5.5 로 풀었다.
모델은 별칭(opus·sonnet·haiku)으로 넘긴다 — ID 를 박으면 새 모델이 나와도 옛 판에 묶인다(사용자 10-30).
같은 규칙의 플러그인 쪽 = brain-base src/engine.ts findClaudeBin · src/sub.ts(구독 확인).

구독 확인(11-11 · 구독 해지 대비) — 돈 드는 호출 없이 신호 여럿:
  ① 과금 길: 환경변수(API 키·게이트웨이·Bedrock·Vertex·Foundry)·~/.claude/settings.json 의 env·apiKeyHelper → 늘 막는다(해지 뒤 종량으로 새지 않게)
  ② `claude auth status --json`(모델 호출 0 · 0.7초): loggedIn=false → 로그인 안 됨 · authMethod≠claude.ai → 구독 아님 ·
     subscriptionType 없음·free → 구독 해지. 다시 로그인·구독하면 다음 확인에서 저절로 풀린다.
  ③ 호출 결과: assistant 줄의 error 칸(CLI 가 붙이는 종류)·오류 글. 실패한 호출은 사용량이 안 든다(11-11 실측: 로그인 없음 = 모델 <synthetic> · 토큰 0).
     해지·로그인 끊김이면 상태 파일에 적고 RETRY 동안 묻지 않는다 → 지나면 한 번 다시 부른다(되면 풀림).
  ⚠ 실제 해지 때 CLI 가 내는 글은 잴 수 없다(구독을 끊지 않는다 · 안 잼). 그래서 글이 아니라 ②의 칸과 ③의 error 종류로 잡는다.
     잰 것 = 로그인 없음(빈 설정 폴더): auth status loggedIn=false · -p = error "authentication_failed" · 글 "Not logged in · Please run /login".
     error 종류 목록(2.1.321 실행 파일 글자): authentication_failed·oauth_org_not_allowed·account_on_hold·verification_required·billing_error·rate_limit·…
  상태 파일 = 3_시스템/_index/subscription.json(플러그인과 같이 씀) {state ok|off, kind, why, since, source status|call, until, alerted}
  알림 = 끊김 한 번에 한 번(alerted) · 풀리면 지운다.

사용:  py -3 3_시스템/claude_bin.py          # 고른 경로와 판
       py -3 3_시스템/claude_bin.py sub      # 구독 확인(상태 파일도 고침 · 알림은 안 띄움)
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "_index", "subscription.json")
LOG = os.path.join(HERE, "_index", "subscription.log")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_cache = None

# 이것들이 있으면 claude 가 구독 대신 API 키·다른 경로(게이트웨이·Bedrock·Vertex)로 나간다. ANTHROPIC_AUTH_TOKEN 은
# `claude auth status` 에 드러나지 않아(10-26 실측) 직접 본다 — 10-02 사고(사용자 환경변수 → 모든 claude 가 게이트웨이로)와 같은 꼴.
PAID_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
NO_LOGIN = "claude 로그인 안 됨"
LAPSED = "구독 해지"
NOT_SUB = "구독 아님"
LOGIN = "로그인 안 됨"
LIMIT = "사용량 한도"
UNKNOWN = "확인 실패"
RETRY = 6 * 3600            # 호출로 잡은 끊김 — 이만큼 묻지 않다가 한 번 다시 부른다(실패한 호출은 사용량 0)
FREE = ("", "free", "none", "null")
# CLI 가 assistant 줄 error 칸에 붙이는 종류(2.1.321 실행 파일 글자) → 우리 갈래
ERR_LAPSED = ("oauth_org_not_allowed", "account_on_hold")
ERR_LOGIN = ("authentication_failed",)
ERR_LIMIT = ("rate_limit", "billing_error")        # billing_error = «usage limit reached — check plan»·크레딧 — 해지로 치지 않는다(오탐 막기)
# 로그인이 없거나 풀렸을 때 내는 말(2.1.287 실행 파일 글자 · 11-02 / 2.1.321 실측 11-11)
LOGIN_TEXT = r"(?i)run /login|not logged in|oauth token (?:revoked|has expired)|login expired|invalid api key|authentication_error|^401$"
# 해지로 보이는 말 — error 칸이 없거나 unknown 일 때만 본다(답 본문에 «구독»이 나와도 끊김이 아니다). 실제 글은 안 잼.
LAPSE_TEXT = r"(?i)(?:subscription|plan) (?:has )?(?:expired|ended|cancel+ed|inactive)|no (?:active )?subscription|does(?: not|n't) have access to claude code|requires? a (?:claude )?(?:pro|max)|구독이 (?:없|해지|만료)"
# 한도 글(2.1.321 실행 파일: «You've hit your limit · resets …»·«/upgrade to keep using Claude Code»·«Upgrade to Max or Ultra …») — 해지 글보다 먼저 본다.
# 11-12 잼: error 칸이 빠지면 «Upgrade to Max» 가 해지로 읽혔다(설치본 0.47.0 · 실제 CLI 는 칸을 달아 오판은 없었음) → 해지 글에서 «upgrade to» 를 빼고 한도 글을 앞에.
LIMIT_TEXT = r"(?i)hit your (?:usage )?limit|usage limit|limit (?:reached|resets)|session limits?|rate.?limit|resets? (?:at )?\d|사용량 한도"


def _ver(s):
    return tuple(int(x) for x in s.split("."))


def candidates():
    """[(판 튜플, 경로, 어디서)] — 판이 높은 순"""
    out = []
    data = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local"), "Claude-Data")
    for p in glob.glob(os.path.join(data, "*", "claude-code", "*", "*", "claude.exe")):
        v = os.path.basename(os.path.dirname(os.path.dirname(p)))
        if re.fullmatch(r"\d+\.\d+\.\d+", v):
            out.append((_ver(v), p, "데스크톱 앱"))
    own = {os.path.normcase(os.path.abspath(x)) for x in (os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe"), shutil.which("claude")) if x and os.path.isfile(x)}
    for p in own:
        try:
            got = subprocess.run([p, "--version"], capture_output=True, timeout=15, creationflags=NO_WINDOW).stdout.decode("utf-8", "replace")  # 창 없는 서버(pyw)에서 불려도 창이 안 뜨게
        except (OSError, subprocess.TimeoutExpired):
            continue
        m = re.search(r"(\d+\.\d+\.\d+)", got)
        if m:
            out.append((_ver(m.group(1)), p, "독립 설치"))
    return sorted(out, reverse=True)


def newest():
    """가장 새 claude 경로(한 번 고르면 이 프로세스 동안 그대로) · 시험 = BRAIN_CLAUDE_BIN"""
    global _cache
    test = os.environ.get("BRAIN_CLAUDE_BIN")
    if test:
        return test
    if _cache is None:
        c = candidates()
        _cache = c[0][1] if c else "claude"
    return _cache


# ───────── 구독 확인 ─────────
def _log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8", newline="\n") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d):
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE)
    except OSError:
        pass


def _off(kind, why, source):
    """끊김 적기 — 같은 끊김이 이어지면 since·alerted 를 그대로 둔다(알림 한 번)"""
    d = load()
    now = int(time.time())
    same = d.get("state") == "off"
    d.update(state="off", kind=kind, why=why[:200], source=source, checked=now)
    if not same:
        d.update(since=now, alerted=None)
        _log(f"끊김 {kind}: {why[:120]} ({source})")
    if source == "call":
        d["until"] = now + RETRY
    else:
        d.pop("until", None)
    _save(d)
    return d


def _ok(source):
    d = load()
    if d.get("state") == "off":
        _log(f"풀림 ({source}) — {d.get('kind')} {int(time.time()) - int(d.get('since') or 0)}초 뒤")
        d = {"state": "ok", "checked": int(time.time()), "back": int(time.time())}
        _save(d)
    elif d.get("state") != "ok":
        _save({"state": "ok", "checked": int(time.time())})
    return d


def paid_route(env=None):
    """구독을 벗어나 과금될 길 — 있으면 까닭, 없으면 ""(이 확인은 끊김이 아니라 늘 막는 것 · 상태 파일에 안 적는다)"""
    from urllib.parse import urlparse
    env = dict(os.environ if env is None else env)
    try:                                                        # --setting-sources user = 사용자 settings.json 의 env 도 claude 에 들어간다
        with open(os.path.join(os.path.expanduser("~"), ".claude", "settings.json"), encoding="utf-8") as f:
            st = json.load(f)
        env.update({k: str(v) for k, v in (st.get("env") or {}).items()})
        if st.get("apiKeyHelper"):
            return "~/.claude/settings.json 에 apiKeyHelper(API 키) 설정"
    except (OSError, ValueError):
        pass
    bad = [n for n in PAID_ENV if env.get(n)]
    base = env.get("ANTHROPIC_BASE_URL")
    if base and urlparse(base).hostname != "api.anthropic.com":
        bad.append(f"ANTHROPIC_BASE_URL={urlparse(base).hostname}")
    return ("환경변수 " + ", ".join(bad)) if bad else ""


def auth_status(env=None):
    """`claude auth status --json` → 사전 · 못 읽으면 None(모델 호출 0) · env = 부를 claude 에 줄 환경(없으면 지금 것)"""
    try:
        with tempfile.TemporaryDirectory(prefix="claude-auth-") as cwd:    # 볼트 밖에서
            r = subprocess.run([newest(), "auth", "status", "--json"], cwd=cwd, env=env, capture_output=True, timeout=60, creationflags=NO_WINDOW)
        d = json.loads(r.stdout.decode("utf-8", "replace"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def judge_status(d):
    """auth status 사전 → (갈래, 까닭) · 구독이면 ("", "")"""
    if d is None:
        return UNKNOWN, "로그인 상태 확인 실패"
    if not d.get("loggedIn"):
        return LOGIN, NO_LOGIN
    if d.get("authMethod") != "claude.ai" or d.get("apiProvider") != "firstParty" or d.get("apiKeySource"):
        return NOT_SUB, f"구독 로그인이 아님(authMethod={d.get('authMethod')} · apiProvider={d.get('apiProvider')} · apiKeySource={d.get('apiKeySource')})"
    plan = str(d.get("subscriptionType") or "").lower()
    if plan in FREE:
        return LAPSED, f"구독이 없음(subscriptionType={d.get('subscriptionType')})"
    return "", ""


LAST = {}                   # 이 프로세스의 마지막 check() — subscription()(까닭 글만)을 부른 쪽이 갈래를 읽는다


def check(env=None):
    """구독으로 부를 수 있나 → {ok, kind, why}. 막는 쪽으로 기운다(모르면 막음). 상태 파일을 고친다(알림은 alert()).
    env = 부를 claude 에 줄 환경(부르는 쪽이 ANTHROPIC_* 를 걷어 넘기면 그것으로 잰다 · 없으면 지금 환경)"""
    st = _check(env)
    LAST.clear()
    LAST.update(st)
    return st


def _check(env):
    why = paid_route(env)
    if why:
        return {"ok": False, "kind": NOT_SUB, "why": why}
    kind, why = judge_status(auth_status(env))
    if kind in (LAPSED, LOGIN):
        _off(kind, why, "status")
        return {"ok": False, "kind": kind, "why": why}
    if kind:                                                    # 구독 아님·확인 실패 — 막되 «끊김»으로 적지는 않는다(해지 화면 오탐 막기)
        return {"ok": False, "kind": kind, "why": why}
    d = load()
    if d.get("state") == "off" and d.get("source") == "call" and time.time() < (d.get("until") or 0):
        return {"ok": False, "kind": d.get("kind") or LAPSED, "why": f"{d.get('why')} · 다시 확인 {time.strftime('%m-%d %H:%M', time.localtime(d['until']))}"}
    if d.get("state") == "off" and d.get("source") == "status":
        _ok("status")                                           # 다시 로그인·구독함
    return {"ok": True, "kind": "", "why": ""}


def subscription():
    """옛 꼴(ingest_vision.subscription) — 맞으면 "", 아니면 까닭"""
    st = check()
    return "" if st["ok"] else st["why"]


def classify(error=None, text="", status=None):
    """호출 하나의 결과 → 갈래(LAPSED·LOGIN·LIMIT) | "" . error = assistant 줄 error 칸 · text = 결과 글·오류 글 · status = api_error_status"""
    e = str(error or "").lower()
    t = str(text or "")
    if e in ERR_LIMIT or (e not in ERR_LAPSED and re.search(LIMIT_TEXT, t)):
        return LIMIT
    if e in ERR_LAPSED or (e in ("", "unknown") + ERR_LOGIN and re.search(LAPSE_TEXT, t)):
        return LAPSED
    if e in ERR_LOGIN or re.search(LOGIN_TEXT, t, re.M) or str(status) == "401":
        return LOGIN
    return ""


def note_call(ok, error=None, text="", status=None):
    """호출을 마친 쪽이 부른다 — 되면 끊김을 풀고, 해지·로그인 끊김이면 적는다. 돌려줌 = 갈래 | "" """
    if ok:
        d = load()
        if d.get("state") == "off" and d.get("source") == "call":
            _ok("call")
        return ""
    kind = classify(error, text, status)
    if kind in (LAPSED, LOGIN):
        _off(kind, (str(error or "") + " " + str(text or "")).strip()[:200] or kind, "call")
    return kind


TITLE = {LAPSED: "구독이 해지되었습니다", LOGIN: "Claude 로그인이 풀렸습니다"}
BODY = {LAPSED: "구독이 필요한 기능(대화창·그림 읽기·공지 판정·폰 RC)을 멈췄습니다. 일정·찾기·수집은 그대로 돕니다. 다시 구독하면 저절로 풀립니다.",
        LOGIN: "구독이 필요한 기능(대화창·그림 읽기·공지 판정·폰 RC)을 멈췄습니다. 대화창이나 claude 에서 다시 로그인하면 풀립니다."}


def alert(toast=True):
    """끊김 알림 — 이 끊김에 아직 안 알렸으면 한 번(윈도 알림) · 알렸으면 False. toast=False = 부른 쪽이 스스로 띄운다(플러그인 알림 등)"""
    d = load()
    if d.get("state") != "off" or d.get("alerted"):
        return False
    d["alerted"] = int(time.time())
    _save(d)
    kind = d.get("kind") if d.get("kind") in TITLE else LAPSED
    _log(f"알림 {'윈도' if toast else '부른 쪽'}: {TITLE[kind]}")
    if toast and not os.environ.get("BRAIN_SUB_NO_TOAST"):
        _toast(TITLE[kind], BODY[kind])
    return True


def _toast(title, body):
    """윈도 알림(초점을 안 뺏음 · 받는 문 door.py 와 같은 앱 이름)"""
    import base64
    from xml.sax.saxutils import escape
    xml = ('<toast><visual><binding template="ToastGeneric"><text>%s</text><text>%s</text></binding></visual>'
           '<audio silent="true"/></toast>') % (escape(title), escape(body))
    ps = ("$null=[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime];"
          "$null=[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom,ContentType=WindowsRuntime];"
          "$x=New-Object Windows.Data.Xml.Dom.XmlDocument;$x.LoadXml(@'\n" + xml + "\n'@);"
          "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Claude_Brain.Door')"
          ".Show((New-Object Windows.UI.Notifications.ToastNotification $x))")
    try:
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(ps.encode("utf-16-le")).decode()],
                         creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def lapsed():
    """상태 파일만 본다(실행 파일을 안 띄움) — 끊김이면 그 사전, 아니면 None"""
    d = load()
    return d if d.get("state") == "off" else None


if __name__ == "__main__":
    if sys.argv[1:2] == ["sub"]:
        print(json.dumps(check(), ensure_ascii=False))
        print(json.dumps(load(), ensure_ascii=False))
    else:
        for v, p, where in candidates():
            print(".".join(map(str, v)), where, p)
        print("고름:", newest())
