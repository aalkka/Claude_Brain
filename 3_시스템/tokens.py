#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""외부뇌 토큰 계측 (lean P1). 세션 트랜스크립트 jsonl → 토큰 회계.

CLI:
  python tokens.py                     최근 20세션 요약표
  python tokens.py --n 46              최근 N세션
  python tokens.py --all               전량
  python tokens.py --session 1dace65b  단일 세션 상세(턴별 누적 출력 곡선)
  python tokens.py --raw out.json      원자료를 파일로 저장(요약만 stdout)

설계 제약(전부 실측에 근거한다)
  - 리스크 1: 계측 자체가 토큰을 쓴다 → stdout은 요약 수치만. 원자료는 --raw 파일로.
  - 자기참조 오염: 세션 로그에는 이 계측기를 논의한 대화가 들어 있다. 문자열 매칭으로 세면
    문서가 자기를 잡는다(실측: `rg -c 'output_style'` 오탐 21 대 실제 5).
    → 판별은 반드시 레코드 구조(type · attachment.type)로 한다.
  - 파일 I/O는 encoding="utf-8" 명시, errors="ignore" 금지.
  - 경로에 버전해시·절대경로를 박지 않는다. 프로젝트 디렉터리는 VAULT에서 유도.
  - 깨진 줄을 조용히 버리지 않는다. bad 열로 보고한다.

표준입력 환산 = input + CW*cache_creation + CR*cache_read (기본 CW=2.0, CR=0.10).
  출력 토큰은 단가가 달라 합산하지 않고 별도 열로 둔다.

모드별 귀속: output_style 어태치먼트(attachment.type == "output_style")에서 활성 스타일명을
  수집한다. 세션 도중 바뀌면 전부 표기한다(업스트림 e9cb843이 고친 귀속 버그를 처음부터 피한다).
"""
import argparse, datetime, json, os, re, sys
from collections import OrderedDict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CW = 2.0    # 캐시 쓰기 배수(표준입력 환산). 실측 2026-08-04: 캐시의 98.4%가 1시간 TTL → 2.0 맞음
CR = 0.10   # 캐시 읽기 배수
MISS_DROP = 0.20   # 읽기가 러닝맥스 대비 이만큼 떨어지면 캐시 미스로 본다
TTL_MIN = 60       # 1시간 TTL. 실측: 공백>=60분이면 예외 없이 미스(20/20)


def _dt(s):
    try:
        return datetime.datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None


def project_dir(vault=VAULT):
    """VAULT 경로 → Claude Code 프로젝트 트랜스크립트 디렉터리. 하드코딩 금지(확정 12)."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", vault)
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", slug)


def is_user_prompt(rec):
    """진짜 유저 프롬프트인가. 도구 결과(tool_result)는 user 레코드지만 턴이 아니다."""
    if rec.get("type") != "user":
        return False
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if not isinstance(content, list):
        return False
    text = ""
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_result":
            return False
        if block.get("type") == "text":
            text += block.get("text") or ""
    return bool(text.strip())


def scan(path):
    """세션 jsonl 1개 → 회계 dict. 실패한 줄은 세되 버리지 않는다."""
    acc = {
        "input": 0, "output": 0, "cache_creation": 0, "cache_read": 0,
        "turns": 0, "assistant": 0, "requests": 0, "sidechain": 0, "bad": 0,
        "text_chars": 0, "tool_chars": 0, "tools": {}, "_names": {},
        "_req": OrderedDict(), "seq": [], "_buf": [], "answers": [],
        "models": OrderedDict(), "styles": OrderedDict(),
        "start": None, "end": None, "curve": [],
        # 캐시 미스 재작성 회계 (2026-08-04 신설)
        "misses": 0, "rewrite": 0, "why": {}, "why_tok": {},
        "_peak": 0, "_pts": None, "_pmdl": None,
    }
    seen_req = set()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (ValueError, TypeError):
                acc["bad"] += 1
                continue
            ts = rec.get("timestamp")
            if ts:
                if acc["start"] is None:
                    acc["start"] = ts
                acc["end"] = ts

            rtype = rec.get("type")
            if rtype == "attachment":
                att = rec.get("attachment") or {}
                if att.get("type") == "output_style":
                    acc["styles"][att.get("style") or "(unnamed)"] = 1
            elif rtype == "user":
                # 도구 결과 유입량. 한 번 들어오면 이후 모든 요청에서 다시 읽힌다
                # → 출력 1자보다 훨씬 비싸다(2026-08-02 실측: 가시 텍스트의 1.1~4.3배).
                blocks = (rec.get("message") or {}).get("content")
                if isinstance(blocks, list):
                    for blk in blocks:
                        if not isinstance(blk, dict) or blk.get("type") != "tool_result":
                            continue
                        body = blk.get("content")
                        size = 0
                        if isinstance(body, str):
                            size = len(body)
                        elif isinstance(body, list):
                            for part in body:
                                if isinstance(part, dict) and part.get("type") == "text":
                                    size += len(part.get("text") or "")
                        name = acc["_names"].get(blk.get("tool_use_id"), "?")
                        slot = acc["tools"].setdefault(name, [0, 0])
                        slot[0] += size
                        slot[1] += 1
                        acc["tool_chars"] += size
                if is_user_prompt(rec):
                    acc["turns"] += 1
                    acc["curve"].append([acc["turns"], acc["output"]])
                    if acc["_buf"]:
                        acc["answers"].append("\n".join(acc["_buf"]))
                        acc["_buf"] = []
            elif rtype == "assistant":
                acc["assistant"] += 1
                if rec.get("isSidechain"):
                    acc["sidechain"] += 1
                msg = rec.get("message") or {}
                if msg.get("model"):
                    acc["models"][msg["model"]] = 1
                rid = rec.get("requestId") or msg.get("id")
                # 가시 텍스트 분량. 레코드는 요청당 여러 개지만 **content 블록은 서로 다르다**
                # (thinking / text / tool_use). usage만 복제되므로 여기선 접지 않는다.
                # 이 값이 압축 규칙의 사정거리다 — 추론·도구 블록은 출력스타일이 못 건드린다.
                blocks = msg.get("content")
                if isinstance(blocks, list):
                    for blk in blocks:
                        if not isinstance(blk, dict):
                            continue
                        if blk.get("type") == "text":
                            acc["text_chars"] += len(blk.get("text") or "")
                            acc["_buf"].append(blk.get("text") or "")
                        elif blk.get("type") == "tool_use":
                            acc["_names"][blk.get("id")] = blk.get("name")
                            acc["_req"].setdefault(rid, []).append(blk.get("name"))

                usage = msg.get("usage") or {}
                if not usage:
                    continue
                # 한 API 요청이 assistant 레코드 여러 개로 쪼개지고 각 레코드가 **같은 usage를
                # 그대로 복사**해 갖는다(실측 2026-08-01: 레코드 120 대 고유 요청 50, 최대 4중복).
                # requestId로 접지 않으면 약 2.4배 과대계상된다.
                if rid is not None:
                    if rid in seen_req:
                        continue
                    seen_req.add(rid)
                acc["requests"] += 1
                cw_ = usage.get("cache_creation_input_tokens") or 0
                cr_ = usage.get("cache_read_input_tokens") or 0
                acc["input"] += usage.get("input_tokens") or 0
                acc["output"] += usage.get("output_tokens") or 0
                acc["cache_creation"] += cw_
                acc["cache_read"] += cr_

                # 캐시 미스 = 읽기가 러닝맥스 대비 급락. 그 시점의 쓰기 = **이미 썼던 프리픽스를
                # 다시 쓴 값**이다. 실측 2026-08-04(전 70여 세션): 캐시쓰기의 74.3%가 재작성이고
                # 이는 세션 총비용의 약 1/3. 기존 회계는 손대지 않는다 — 07-27·08-02 수치와의
                # 비교 가능성을 깨지 않기 위해 **추가만** 한다.
                mdl_ = msg.get("model")
                if mdl_ != "<synthetic>":   # 로컬 합성 레코드는 API 호출이 아니다(급락 오탐원)
                    if acc["_peak"] and cr_ < acc["_peak"] * (1 - MISS_DROP):
                        gap = None
                        t0, t1 = _dt(acc["_pts"]), _dt(ts)
                        if t0 and t1:
                            gap = (t1 - t0).total_seconds() / 60.0
                        if mdl_ and acc["_pmdl"] and mdl_ != acc["_pmdl"]:
                            why = "모델전환"
                        elif gap is not None and gap >= TTL_MIN:
                            why = "TTL만료"
                        else:
                            why = "미상"
                        acc["misses"] += 1
                        acc["rewrite"] += cw_
                        acc["why"][why] = acc["why"].get(why, 0) + 1
                        acc["why_tok"][why] = acc["why_tok"].get(why, 0) + cw_
                    acc["_peak"] = max(acc["_peak"], cr_)
                    acc["_pts"] = ts or acc["_pts"]
                    acc["_pmdl"] = mdl_ or acc["_pmdl"]

    acc["in_std"] = int(acc["input"] + CW * acc["cache_creation"] + CR * acc["cache_read"])
    acc["seq"] = list(acc["_req"].values())
    if acc["_buf"]:
        acc["answers"].append("\n".join(acc["_buf"]))
    return acc


READ_T = {"Read", "Grep", "Glob", "WebFetch", "WebSearch"}
EDIT_T = {"Edit", "Write", "NotebookEdit"}
EXEC_T = {"Bash", "PowerShell"}


def tool_class(name):
    return ("read" if name in READ_T else "edit" if name in EDIT_T
            else "exec" if name in EXEC_T else "etc")


def print_batch(row):
    """배치 구조. 규칙(CLAUDE.md §2 도구) 준수의 직접 지표.

    ⚠ 배치율은 **작업 성격에 좌우된다** — 2026-08-02 실측에서 read 43%→8% 구간에
    배치율 1.48→1.02가 동행했다. 구성비 없이 주차를 비교하면 교락된다. 항상 같이 본다.
    """
    seq = row["seq"]
    if not seq:
        return
    n = len(seq)
    tools = [t for s in seq for t in s]
    comp = {}
    for t in tools:
        k = tool_class(t)
        comp[k] = comp.get(k, 0) + 1
    tot = len(tools) or 1

    runs, wasted = {}, {}
    i = 0
    while i < n:
        if len(seq[i]) != 1:
            i += 1
            continue
        k = tool_class(seq[i][0])
        j = i
        while j + 1 < n and len(seq[j + 1]) == 1 and tool_class(seq[j + 1][0]) == k:
            j += 1
        if j - i + 1 >= 2:
            runs[k] = runs.get(k, 0) + 1
            wasted[k] = wasted.get(k, 0) + (j - i)
        i = j + 1

    print("\n배치 구조 — 도구요청 {} · 평균 {:.2f}개/요청".format(n, len(tools) / n))
    print("  구성비  " + " ".join("%s %.0f%%" % (k, 100.0 * comp.get(k, 0) / tot)
                                 for k in ("read", "edit", "exec")))
    if runs:
        print("  연속 단독런  " + " ".join("%s %d런/낭비%d" % (k, runs[k], wasted[k])
                                        for k in ("read", "edit", "exec") if k in runs))
        w = sum(wasted.values())
        print("  → 명백 절약가능 요청 %d / %d = %.0f%%  (기준선 개발 37~43%%·설계 21%%·리서치 10%%)"
              % (w, n, 100.0 * w / n))


def collect(directory):
    if not os.path.isdir(directory):
        sys.exit("트랜스크립트 디렉터리 없음: %s" % directory)
    out = []
    for name in os.listdir(directory):
        if not name.endswith(".jsonl"):
            continue
        full = os.path.join(directory, name)
        row = scan(full)
        row["sid"] = name[:8]
        row["path"] = full
        row["mtime"] = os.path.getmtime(full)
        out.append(row)
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return out


def short(ts):
    return (ts or "")[:16].replace("T", " ")


def print_summary(rows):
    head = ("sid", "model", "turn", "output", "가시%", "in_std", "cache_r", "style", "bad", "start")
    fmt = "{:<9}{:<16}{:>5}{:>9}{:>7}{:>10}{:>11}  {:<14}{:>4}  {}"
    print(fmt.format(*head))
    print("-" * 104)
    tot = {"turns": 0, "output": 0, "in_std": 0, "bad": 0}
    for r in rows:
        models = ",".join(r["models"]) or "-"
        models = models.replace("claude-", "")
        styles = ",".join(r["styles"]) or "(default)"
        vis = "-" if not r["output"] else "{:.0f}%".format(100.0 * (r["text_chars"] / 1.4) / r["output"])
        print(fmt.format(
            r["sid"], models[:15], r["turns"], r["output"], vis, r["in_std"],
            r["cache_read"], styles[:13], r["bad"], short(r["start"]),
        ))
        for k in tot:
            tot[k] += r[k]
    print("-" * 104)
    print("세션 {}개 · 턴 {} · 출력 {} · 표준입력환산 {} (CW={} CR={}) · 깨진줄 {}".format(
        len(rows), tot["turns"], tot["output"], tot["in_std"], CW, CR, tot["bad"]))
    if tot["bad"]:
        print("⚠ 깨진 줄이 있다. 조용히 버리지 않았으니 원인을 확인할 것.")


def print_detail(row):
    print("세션 {}  모델 {}  스타일 {}".format(
        row["sid"], ",".join(row["models"]) or "-", ",".join(row["styles"]) or "(default)"))
    print("기간 {} ~ {}".format(short(row["start"]), short(row["end"])))
    print("턴 {} · API 요청 {} · assistant 레코드 {} (사이드체인 {}) · 깨진줄 {}".format(
        row["turns"], row["requests"], row["assistant"], row["sidechain"], row["bad"]))
    print("input {} · output {} · cache_creation {} · cache_read {} · 표준입력환산 {}".format(
        row["input"], row["output"], row["cache_creation"], row["cache_read"], row["in_std"]))
    vis_tok = row["text_chars"] / 1.4
    print("가시 텍스트 {}자 ≈ {:.0f}tok = 출력의 {:.0f}%  ← 압축 규칙의 사정거리".format(
        row["text_chars"], vis_tok, 100.0 * vis_tok / row["output"] if row["output"] else 0))
    print("  ⚠ 자↔토큰 환산 1.4는 XLM-R 대리지표(한국어 산문 기준). 절대값 아님, 비율 비교용.")
    print_tools(row)
    print_miss(row)
    print_batch(row)
    print("\n턴별 누적 출력(턴 시작 시점 기준) — DoD-2의 비용 쪽 절반")
    print("{:>5}{:>12}{:>12}".format("turn", "누적출력", "직전턴증분"))
    prev = 0
    for turn, cum in row["curve"]:
        print("{:>5}{:>12}{:>12}".format(turn, cum, cum - prev))
        prev = cum
    print("{:>5}{:>12}{:>12}".format("end", row["output"], row["output"] - prev))


def print_tools(row, top=5):
    """도구 결과 유입량. 컨텍스트에 한 번 들어오면 이후 모든 요청에서 다시 읽힌다."""
    ratio = (row["tool_chars"] / row["text_chars"]) if row["text_chars"] else 0
    print("\n도구 결과 {}자 / 가시 텍스트 {}자 = **{:.1f}배** — C축 1번 레버".format(
        format(row["tool_chars"], ","), format(row["text_chars"], ","), ratio))
    ranked = sorted(row["tools"].items(), key=lambda kv: kv[1][0], reverse=True)[:top]
    for name, (chars, calls) in ranked:
        print("  {:<22}{:>10}자{:>5}회  평균 {:>6}".format(
            name, format(chars, ","), calls, chars // calls if calls else 0))


def print_miss(row):
    """캐시 미스 재작성 회계. **C축 최대 항목** — 전 세션 실측 2026-08-04.

    읽기가 러닝맥스에서 급락한 요청 = 프리픽스를 캐시에서 못 찾은 요청이고, 그때의 쓰기는
    이미 한 번 쓴 것을 다시 쓴 값이다. 전 세션 캐시쓰기 50.4M 중 37.5M(74.3%)이 여기였다.
    회수가 아니라 **토큰으로** 볼 것 — TTL만료는 드물지만(9%) 토큰은 최대(41%)다.
    """
    if not row["requests"] or not row["misses"]:
        return
    share = 100.0 * row["rewrite"] / row["cache_creation"] if row["cache_creation"] else 0
    print("\n캐시 미스 {}회 / 요청 {} · 재작성 {} tok = 캐시쓰기의 {:.1f}%  ← C축 1번 항목".format(
        row["misses"], row["requests"], format(row["rewrite"], ","), share))
    for why in ("TTL만료", "모델전환", "미상"):
        if row["why"].get(why):
            print("  {:<8}{:>4}회{:>16} tok".format(
                why, row["why"][why], format(row["why_tok"].get(why, 0), ",")))
    if row["why"].get("TTL만료"):
        print("  ⚠ TTL만료 = 1시간 이상 자리 비움. 공백>=60분이면 예외 없이 미스(실측 20/20).")
    if row["why"].get("모델전환"):
        print("  ⚠ 캐시는 모델별로 잡힌다. 세션 중 모델을 바꾸면 프리픽스 전량 무효.")


TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.M)
CODE_SPAN = re.compile(r"`[^`\n]*`")
INLINE_MATH = re.compile(r"(?<!\$)\$(?!\$)[^\$\n]{1,80}\$(?!\$)")
CONF_MARK = re.compile(r"미검증|실측|추정|측정(?:됨|된|되지)|가정|〔[^〕]{1,12}〕")


def print_quality(row):
    """출력 품질 규칙 준수의 직접 지표. 기준선은 제작자 볼트 실측(2026-08-02)."""
    ans = row.get("answers") or []
    if not ans:
        return
    lens = sorted(len(a) for a in ans)
    med = lens[len(lens) // 2]
    body = "\n".join(ans)
    if not body:
        return

    tables = []
    for a in ans:
        run = 0
        for ln in a.split("\n"):
            if TABLE_ROW.match(ln):
                run += 1
            else:
                if run >= 3:
                    tables.append(run - 2)   # 헤더+구분선 제외 = 데이터 행
                run = 0
        if run >= 3:
            tables.append(run - 2)
    small = [t for t in tables if t < 3]

    # 코드 스팬을 지운 뒤 인라인 수식을 센다(`$var` 오탐 제거)
    stripped = CODE_SPAN.sub("", body)
    inline = INLINE_MATH.findall(stripped)
    conf = CONF_MARK.findall(body)

    print("\n출력 품질 지표")
    print("  답변 %d개 · 답변당 가시자 중앙값 %d자   (기준선 2,426)" % (len(ans), med))
    if tables:
        print("  표 %d개 · 데이터행 중앙값 %d · 3행 미만 %d개(%.0f%%)   (기준선 13%%)"
              % (len(tables), sorted(tables)[len(tables) // 2], len(small),
                 100.0 * len(small) / len(tables)))
    print("  인라인 $…$ %d회   (기준선 3 — 렌더 안 되므로 감소해야 정상)" % len(inline))
    print("  확신도 표기 %d회 (답변당 %.1f)" % (len(conf), len(conf) / len(ans)))


def main():
    ap = argparse.ArgumentParser(description="외부뇌 토큰 계측 (lean P1)")
    ap.add_argument("--n", type=int, default=20, help="최근 N세션 (기본 20)")
    ap.add_argument("--all", action="store_true", help="전량")
    ap.add_argument("--session", help="세션 ID 접두 → 상세")
    ap.add_argument("--dir", default=None, help="트랜스크립트 디렉터리 override")
    ap.add_argument("--tools", action="store_true", help="세션별 도구 결과 유입량 내역")
    ap.add_argument("--batch", action="store_true", help="배치 구조(연속 단독런·구성비)")
    ap.add_argument("--miss", action="store_true", help="캐시 미스 재작성 회계(원인 귀속)")
    ap.add_argument("--quality", action="store_true", help="출력 품질 지표(§5 준수)")
    ap.add_argument("--raw", help="원자료 JSON 저장 경로 (stdout은 요약만)")
    args = ap.parse_args()

    rows = collect(args.dir or project_dir())

    if args.session:
        hit = [r for r in rows if r["sid"].startswith(args.session)]
        if not hit:
            sys.exit("세션 없음: %s" % args.session)
        print_detail(hit[0])
        rows = hit
    else:
        if not args.all:
            rows = rows[: args.n]
        print_summary(rows)
        if args.tools or args.batch or args.quality or args.miss:
            for r in rows:
                print("\n=== %s" % r["sid"])
                if args.tools:
                    print_tools(r)
                if args.miss:
                    print_miss(r)
                if args.batch:
                    print_batch(r)
                if args.quality:
                    print_quality(r)

    if args.raw:
        dump = []
        for r in rows:
            item = {k: v for k, v in r.items()
                    if k not in ("models", "styles", "_names", "_req", "_buf", "answers",
                                 "_peak", "_pts", "_pmdl")}
            item["models"] = list(r["models"])
            item["styles"] = list(r["styles"])
            dump.append(item)
        with open(args.raw, "w", encoding="utf-8") as fh:
            json.dump(dump, fh, ensure_ascii=False, indent=2)
        print("\n원자료 → %s" % args.raw)


if __name__ == "__main__":
    main()
