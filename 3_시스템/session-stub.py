# -*- coding: utf-8 -*-
"""세션 스텁 갱신 (결정론층 — LLM 호출 없음).

Stop 훅이 매 턴 **디태치**로 부른다. 트랜스크립트를 증분 파싱해 이벤트를 누적하고
`3_시스템/_index/stubs/<sid>.md` 를 다시 렌더링한다.

왜 있나: 세션이 커지면 재개 1회에 20만~80만 토큰이 재작성된다(실측 2026-08-07,
지출의 29%). 스텁이 있으면 그 세션을 **다시 열지 않고** 새 세션에서 색인만 읽고
이어갈 수 있다 — in_std 170만 대 4만.

경계: 요약이 아니라 색인이다. '왜'·'결정'은 담지 않는다(LLM 없이는 불가능).
그건 산출물 노트에 이미 있고, 스텁은 그것을 가리킨다.

사용:  python session-stub.py <transcript.jsonl> [--out DIR] [--full]
"""
import json, os, sys, re, time, datetime as dt
from collections import Counter

KST = dt.timedelta(hours=9)
VAULT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DENY = [("requested permissions to", r"permissions to (?:\w+ to )?(\S+)", "권한미승인"),
        ("doesn't want to proceed", None, "사용자거부")]
FOLD = {"수정", "신규", "읽기", "조회", "실행"}
PTR = {"발화", "재작성", "거부", "실패"}
MARK = {"발화": "U:", "진행": ">", "재작성": "!!", "거부": "X", "실패": "x", "스킬": "S:"}
CORE_RX = r"(CLAUDE\.md|3_시스템/(hooks|search\.py|conventions\.md)|\.claude/settings\.json)"
BIG_LINE = 200_000        # 이 크기를 넘는 줄이 있으면 헤더에 Read 경고를 단다
STATE_V = 2               # 상태 스키마 버전 — 올리면 다음 실행이 전량 재파싱


def rel(p):
    return p.replace(VAULT + "\\", "").replace(VAULT + "/", "").replace("\\", "/")


def new_state():
    return {"v": STATE_V, "offset": 0, "ev": [], "seen": [], "peak": 0, "prevreq": None,
            "t0": None, "t1": None, "ver": [], "mdl": [], "skills": [], "tools": {},
            "maxctx": 0, "written": [], "readset": [], "bigline": 0}


def scan(path, st):
    """offset 이후만 파싱해 상태에 누적. 상태는 JSON 직렬화 가능한 형태로 유지."""
    seen = set(st["seen"]); written = set(st["written"]); readset = set(st["readset"])
    tools = Counter(st["tools"]); ver = list(st["ver"]); mdl = set(st["mdl"])
    skills = set(st["skills"]); ev = st["ev"]
    peak = st["peak"]; maxctx = st["maxctx"]; bigline = st["bigline"]
    prevreq = st["prevreq"]
    # 줄 번호는 offset 기준으로 이어 세야 한다 — 상태에 마지막 줄번호를 둔다
    ln = st.get("lastline", 0)
    with open(path, "rb") as fh:
        fh.seek(st["offset"])
        raw = fh.read()
    # 마지막 개행 이후는 아직 쓰이는 중일 수 있다 — 다음 회차로 미룬다
    cut = raw.rfind(b"\n")
    if cut < 0:
        return st, False
    consumed = cut + 1
    for bline in raw[:cut].split(b"\n"):
        ln += 1
        if len(bline) > bigline:
            bigline = len(bline)
        if not bline.strip():
            continue
        try:
            d = json.loads(bline.decode("utf-8", "replace"))
        except Exception:
            continue
        ts = d.get("timestamp")
        if ts:
            st["t0"] = st["t0"] or ts
            st["t1"] = ts
        typ = d.get("type")
        if typ == "user":
            c = (d.get("message") or {}).get("content")
            if isinstance(c, str) and c.strip() and not c.lstrip().startswith("<"):
                ev.append([ts, "발화", c.strip().replace("\n", " ")[:400], ln])
            elif isinstance(c, list):
                for b in c:
                    if not isinstance(b, dict) or b.get("type") != "tool_result":
                        continue
                    s = b.get("content")
                    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
                    hit = None
                    for key, rx, lab in DENY:
                        if key in s[:400]:
                            tgt = ""
                            if rx:
                                mm = re.search(rx, s[:300])
                                if mm:
                                    tgt = rel(mm.group(1).rstrip(",."))
                            hit = (lab + " " + tgt).strip()
                            break
                    if hit:
                        ev.append([ts, "거부", hit[:110], ln])
                    elif b.get("is_error"):
                        ev.append([ts, "실패", s[:110].replace("\n", " "), ln])
            continue
        if typ != "assistant":
            continue
        m = d.get("message") or {}
        if d.get("version"):
            ver.append(d["version"])
        if m.get("model") and m["model"] != "<synthetic>":
            mdl.add(m["model"])
        u = m.get("usage"); rid = d.get("requestId")
        if u and rid and rid not in seen:
            seen.add(rid)
            cc = u.get("cache_creation_input_tokens", 0) or 0
            cr = u.get("cache_read_input_tokens", 0) or 0
            if peak and cr < peak * 0.8 and cc >= 50000:
                g = 0.0
                if prevreq and ts:
                    g = (dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                         - dt.datetime.fromisoformat(prevreq.replace("Z", "+00:00"))).total_seconds() / 60
                ev.append([ts, "재작성", "{:,}tok 공백{:.0f}분".format(cc, g), ln])
            peak = max(peak, cc + cr); maxctx = max(maxctx, cc + cr); prevreq = ts
        for b in (m.get("content") or []):
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                for h in re.findall(r"^#{2,4} (.+)$", b.get("text", ""), re.M):
                    ev.append([ts, "진행", h.strip()[:150], ln])
            elif b.get("type") == "tool_use":
                n = b.get("name"); tools[n] += 1; inp = b.get("input") or {}
                fp = inp.get("file_path", "")
                if n == "Write" and fp:
                    kind = "수정" if (fp in written or fp in readset) else "신규"
                    written.add(fp); ev.append([ts, kind, rel(fp), ln])
                elif n in ("Edit", "NotebookEdit") and fp:
                    ev.append([ts, "수정", rel(fp), ln])
                elif n in ("Bash", "PowerShell"):
                    c = inp.get("description") or inp.get("command", "")[:70]
                    if c:
                        ev.append([ts, "실행", c.replace("\n", " ")[:120], ln])
                elif n == "Read" and fp:
                    readset.add(fp); ev.append([ts, "읽기", rel(fp), ln])
                elif n in ("WebFetch", "WebSearch"):
                    ev.append([ts, "조회", (inp.get("url") or inp.get("query", ""))[:110], ln])
                elif n == "Skill":
                    sk = inp.get("skill", ""); skills.add(sk); ev.append([ts, "스킬", sk, ln])
    st.update(offset=st["offset"] + consumed, ev=ev, seen=sorted(seen), peak=peak,
              prevreq=prevreq, ver=ver, mdl=sorted(mdl), skills=sorted(skills),
              tools=dict(tools), maxctx=maxctx, written=sorted(written),
              readset=sorted(readset), bigline=bigline, lastline=ln)
    return st, True


def fold(ev, thr):
    out = []; i = 0
    while i < len(ev):
        k = ev[i][1]
        if k in FOLD:
            j = i
            while j < len(ev) and ev[j][1] == k:
                j += 1
            g = ev[i:j]
            if len(g) >= thr:
                uniq = sorted({x[2] for x in g})
                nm = [x.split("/")[-1] if k in ("수정", "신규", "읽기") else x for x in uniq]
                out.append([g[0][0], k, "{}건 ".format(len(g)) + " | ".join(nm), g[0][3], g[-1][0]])
            else:
                for x in g:
                    out.append([x[0], x[1], x[2], x[3], None])
            i = j
            continue
        e = ev[i]; out.append([e[0], e[1], e[2], e[3], None]); i += 1
    return out


def render(st, path):
    ev = st["ev"]
    thr = 3 if len(ev) < 400 else (5 if len(ev) < 800 else 8)
    tl = fold(ev, thr)
    P = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
    hm = lambda s: (P(s) + KST).strftime("%H:%M") if s else "--:--"
    t0, t1 = P(st["t0"]), P(st["t1"])
    S = []; A = S.append
    A("# 세션 스텁 " + os.path.basename(path)[:8])
    A("자동생성(LLM 미사용). 색인이지 요약이 아니다 — '왜'·'결정'·'무엇을 기각했나'는 없다.")
    A("원본: {} ({:.1f}MB, 보존 30일). [L숫자] = 이 파일의 줄번호.".format(path, os.path.getsize(path) / 1e6))
    if st["bigline"] >= BIG_LINE:
        A("⚠ 이 트랜스크립트엔 최대 {:.1f}MB짜리 줄이 있다. Read(offset=) 로 열지 말 것 — "
          "`python -c \"import itertools,sys;print(next(itertools.islice(open(P,encoding='utf-8'),N-1,N))[:4000])\"` 처럼 "
          "해당 줄만 잘라 읽어라.".format(st["bigline"] / 1e6))
    A("")
    if t0:
        a = t0 + KST; b = t1 + KST
        end = b.strftime("%H:%M") if a.date() == b.date() else b.strftime("%m-%d %H:%M")
        dur = (t1 - t0).total_seconds() / 60
        durs = "{:.0f}분".format(dur) if dur < 600 else "{:.1f}시간 ⚠장기미종료".format(dur / 60)
        A("기간 {}~{} ({}) · 요청 {} · 최대컨텍스트 {:,}tok{}".format(
            a.strftime("%Y-%m-%d %H:%M"), end, durs, len(st["seen"]), st["maxctx"],
            " ⚠100K초과" if st["maxctx"] >= 100000 else ""))
    mdls = st["mdl"]
    A("모델 {}{}{}{}".format(
        ",".join(mdls) or "-",
        " ⚠세션중 모델전환=전량재작성" if len(mdls) > 1 else "",
        " · 버전 " + ",".join(sorted(set(st["ver"]))) if st["ver"] else "",
        " · 스킬 " + ",".join(st["skills"]) if st["skills"] else ""))
    new = sorted({e[2] for e in ev if e[1] == "신규"})
    moc = [p for p in new if re.match(r"2_지식/(notes|decisions|modules)/", p)]
    sess = [p for p in new if p.startswith("2_지식/sessions/")]
    core = sorted({e[2] for e in ev if e[1] in ("신규", "수정") and re.match(CORE_RX, e[2])})
    rw = [e for e in ev if e[1] == "재작성"]
    A("")
    A("## session-close 재료")
    A("- 신규 {} · MOC 등재 대상 {}: {}".format(len(new), len(moc), ", ".join(moc) or "없음"))
    if moc:
        A("- ※ 이 세션의 결론·결정은 위 산출물 노트 안에 있다. 세션 노트를 쓰려면 그것부터 읽어라.")
    if sess:
        A("- 세션노트 기존: " + ", ".join(sess))
    if core:
        A("- ⚠ 코어 접촉(코어 게이트 대상): " + ", ".join(core))
    tot = sum(int(e[2].split("tok")[0].replace(",", "")) for e in rw) if rw else 0
    A("- 실패 {} · 거부 {}{}".format(
        sum(1 for e in ev if e[1] == "실패"), sum(1 for e in ev if e[1] == "거부"),
        " · 캐시재작성 {}건 합 {:,}tok (in_std {:.2f}M)".format(len(rw), tot, 2.0 * tot / 1e6)
        if rw else " · 캐시재작성 0"))
    A("")
    A("## 타임라인 {}줄 / 이벤트 {} (연속 {}건 이상은 한 줄로 접음, 이름은 전부 유지)".format(
        len(tl), len(ev), thr))
    A("U:사용자발화  >Claude진행(응답헤딩)  !!캐시재작성  X거부  x실패  S:스킬")
    ph = None
    for ts, k, c, ln, t2 in tl:
        h = hm(ts)
        if t2 is not None and hm(t2) != h:
            h = h + "~" + hm(t2)
        stamp = h if h != ph else "  ·  "
        ph = h
        p = " [L{}]".format(ln) if k in PTR else ""
        A("{} {} {}{}".format(stamp, MARK.get(k, k), c, p))
    A("")
    A("도구: " + " ".join("{}{}".format(k, v) for k, v in Counter(st["tools"]).most_common(8)))
    return "\n".join(S)


def main():
    argv = sys.argv[1:]
    skip = {argv.index("--out") + 1} if "--out" in argv else set()
    args = [a for i, a in enumerate(argv) if not a.startswith("--") and i not in skip]
    path = args[0] if args else None
    if not path:
        # Stop 훅으로 호출된 경우 — 인자 없이 stdin으로 JSON이 온다.
        # 훅 계약을 우리가 못 지키면 조용히 빠진다(fail-open): 스텁은 부가 기능이고,
        # 여기서 실패해도 세션 진행을 막아선 안 된다.
        try:
            path = (json.loads(sys.stdin.read()) or {}).get("transcript_path")
        except Exception:
            return 0
    if not path or not os.path.exists(path):
        return 0
    outdir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else \
        os.path.join(VAULT, "3_시스템", "_index", "stubs")
    os.makedirs(outdir, exist_ok=True)
    sid = os.path.basename(path).split(".")[0]
    short = sid[:8]
    lock = os.path.join(outdir, ".lock-" + short)
    # 겹침 방지 — 이전 회차가 아직 돌고 있으면 이번은 건너뛴다(다음 턴이 따라잡는다)
    try:
        if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 60:
            return 0
        open(lock, "w").close()
    except OSError:
        pass
    try:
        spath = os.path.join(outdir, ".state-" + short + ".json")
        st = None
        if "--full" not in sys.argv and os.path.exists(spath):
            try:
                st = json.load(open(spath, encoding="utf-8"))
                if st.get("v") != STATE_V or st["offset"] > os.path.getsize(path):
                    st = None          # 스키마 변경·파일 축소 → 전량 재파싱
            except Exception:
                st = None
        st = st or new_state()
        st, changed = scan(path, st)
        if not changed and os.path.exists(os.path.join(outdir, short + ".md")):
            return 0
        json.dump(st, open(spath, "w", encoding="utf-8"), ensure_ascii=False)
        with open(os.path.join(outdir, short + ".md"), "w", encoding="utf-8") as fh:
            fh.write(render(st, path))
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
