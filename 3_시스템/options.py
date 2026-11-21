#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기능 단계(내부 값 high·low·off · 화면 이름 높음·낮음·끔 = NAMES) — 읽기 규칙 · 쓰기 · 추천. 설계 = 외부뇌 «기능 단계와 추천 옵션» §3·§4(11-06).

파일 둘:
  선언    3_시스템/options.registry.json(코어) + 켜진 모듈 module.json 의 contributes.options — git · 배포
  고른 값 3_시스템/options.local.json — 이 PC · git 밖 · 없으면 모두 high

읽기(훅·대본):  import options; options.level("search.semantic")  → "high" | "low" | "off"  (어떤 오류도 "high")

  py -3 3_시스템/options.py get <id>
  py -3 3_시스템/options.py show [--json]
  py -3 3_시스템/options.py set <id> <high|low|off> [--via 곳]
  py -3 3_시스템/options.py battery <same|lower> [--via 곳]
  py -3 3_시스템/options.py preset <high|recommended|min> [--via 곳]
  py -3 3_시스템/options.py recommend [--new-only] [--json]   재서 추천(60~90초) → _index/options/recommend-*.json · 고른 값은 안 씀
  py -3 3_시스템/options.py apply [--file F] [--set id=단계 ...] [--battery same|lower] [--new-only] [--via 곳]   추천을 확정해 씀
  py -3 3_시스템/options.py reset [--via 곳]                    깨진 고른 값 파일을 옆으로 치우고 새로(모두 high)
  py -3 3_시스템/options.py check [--json]                      선언 ↔ 코드 대조 · 안전 파일이 옵션을 안 읽는지
  py -3 3_시스템/options.py migrate [--via 곳]                  옛 칸 값을 나뉜 칸으로(선언 from) · 쓰는 명령이 먼저 부른다

단계 이름 = 선언 labels(켬/끔 동작은 levels [high, off] + labels 켬·끔 · 사용자 11-20 «각 기능별로 나눌 것») · 없으면 NAMES. 내부 값은 그대로 high·low·off.

읽기 규칙(모든 읽는 쪽이 같음 — brain-base src/options.ts · hooks/options-level.ps1):
  1 파일 없음 → high  2 깨짐·객체 아님·schema 모름 → high(파일은 고치지도 지우지도 않음)  3 levels 에 없는 기능 → high
  4 선언 단계 밖 값 → high(한 단계 내리지 않음)  5 선언에 없는 id → 무시(지우지 않음)  6 선언 파일 없음·깨짐 → high
  7 이 판이 모르는 단계 → high  8 preset 은 읽지 않음  9 battery "lower" + 지금 배터리 → high 인 것 중 low 가 있는 것만 low
  ready false 인 기능은 high. needs(장치 이름 목록)에 이 기기 device.json caps 가 거짓인 것이 있으면 그 기능은 없음(칸 안 보임 · 모르면 있음).
  level_needs·labels_without(단계별 장치 조건 · _norm) · battery_keep true = 배터리 낮춤에서 뺌.
  안전 기능(코어 게이트·민감 검사)은 이 파일을 읽지 않는다(check 가 지킨다).
"""
import json
import os
import re
import sys
import time

LEVELS = ("high", "low", "off")
NAMES = {"high": "높음", "low": "낮음", "off": "끔"}  # 화면·출력 이름 — 내부 값과 고른 값 파일은 그대로(사용자 11-07 고름 = 이름 후보 2)
BATTERY = ("same", "lower")
SCHEMA = 1
SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
ID_RX = re.compile(r"^[a-z][a-z0-9_-]*(\.[a-z0-9_-]+)*$")
NOWIN = 0x08000000 if os.name == "nt" else 0


class OptErr(Exception):
    pass


def _v(vault):
    return vault or VAULT


def local_path(vault=None):
    return os.path.join(_v(vault), "3_시스템", "options.local.json")


def registry_path(vault=None):
    return os.path.join(_v(vault), "3_시스템", "options.registry.json")


def out_dir(vault=None):
    return os.path.join(_v(vault), "3_시스템", "_index", "options")


def device_path(vault=None):
    """이 기기에 있는 장치(caps) — 모듈 probe 가 재서 씀 · git 밖(_index) · 선언 needs 가 읽는다."""
    return os.path.join(_v(vault), "3_시스템", "_index", "device.json")


def schema_ok(x):
    """판 번호 1 — 숫자 1(1.0 도) · 참/거짓·글자는 아님(TS·PS 판과 같게)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == SCHEMA


def _load(p):
    """(값, 상태) — 상태 = ok · missing · broken."""
    try:
        with open(p, "rb") as f:
            b = f.read()
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "broken"
    try:
        return json.loads(b.decode("utf-8-sig")), "ok"
    except (ValueError, UnicodeDecodeError):
        return None, "broken"


# ── 선언 ─────────────────────────────────────────────────────────────
def _valid(f):
    return (isinstance(f, dict) and isinstance(f.get("id"), str) and ID_RX.match(f["id"]) is not None
            and isinstance(f.get("levels"), list) and "high" in f["levels"])


def _installed(f, vault):
    """owner 를 적은 코어 선언은 그 대본이 하나라도 있어야 이 볼트의 기능이다 — 다 없으면 «그 기능 없음»으로 뺀다.
    11-16: 배포판에 개인 층 대본이 주인인 «아침 받기» 칸이 보이고 check 가 «owner 없음» 둘로 실패했다. 일부만 없으면 지금처럼 check 가 잡는다.
    주인은 폴더여도 된다(S6 · «로그인 출처 아침 받기» = 3_시스템/collect/browser — 로그인 출처를 만든 볼트에만 칸이 생긴다)."""
    own = [o for o in f.get("owner") or [] if isinstance(o, str)] if isinstance(f.get("owner"), list) else []
    return not own or any(os.path.exists(os.path.join(_v(vault), o)) for o in own)


def caps(vault=None):
    """이 기기 장치 표 {이름: 참/거짓} — 파일이 없거나 깨지면 {}(= 모름 → 칸을 숨기지 않음)."""
    d, st = _load(device_path(vault))
    c = d.get("caps") if st == "ok" and isinstance(d, dict) else None
    return c if isinstance(c, dict) else {}


def capable(f, cs):
    """선언 needs(장치 이름 목록)가 이 기기에 있나 — 잰 값이 거짓인 것이 하나라도 있으면 그 칸은 없음(11-20 자체 절전 범용화:
    덮개 없는 데스크톱·외장 그래픽 없는 노트북에 그 줄을 안 보임). 모르는 장치(아직 안 잼)는 있는 것으로 — 숨겨서 못 쓰는 것보다 낫다."""
    nd = f.get("needs") if isinstance(f, dict) else None
    if not isinstance(nd, list):
        return True
    return not any(isinstance(n, str) and cs.get(n) is False for n in nd)


def label(f, lvl):
    """그 기능의 단계 이름 — 선언 labels(예 켬·끔 · 세션마다·6시간마다) · 없으면 높음·낮음·끔(NAMES)."""
    lb = f.get("labels") if isinstance(f, dict) else None
    v = lb.get(lvl) if isinstance(lb, dict) else None
    return v if isinstance(v, str) and v.strip() else NAMES.get(lvl, lvl)


def _norm(f, source, cs=None):
    """선언 다듬기 — cs(이 기기 장치 표)가 있으면 단계별 장치 조건을 건다(11-20 자체 절전 «재우는 꼴» 셋 중 하나):
    level_needs {단계: [장치]} = 그 장치가 «없음»이면 그 단계를 고를 수 없음(high 는 빼지 않음 — 기본값이라서) ·
    labels_without {장치: {단계: 이름}} = 그 장치가 «없음»이면 그 단계 이름을 바꿈(예 최대 절전이 없으면 high 이름 = 절전)."""
    g = dict(f)
    g["levels"] = [x for x in f["levels"] if isinstance(x, str)]
    cs = cs or {}
    ln = f.get("level_needs") if isinstance(f.get("level_needs"), dict) else {}
    g["levels"] = [x for x in g["levels"] if x == "high" or not (isinstance(ln.get(x), list) and any(isinstance(n, str) and cs.get(n) is False for n in ln[x]))]
    lw = f.get("labels_without") if isinstance(f.get("labels_without"), dict) else {}
    for cap, names in lw.items():
        if cs.get(cap) is False and isinstance(names, dict):
            g["labels"] = {**(g.get("labels") if isinstance(g.get("labels"), dict) else {}), **{k: v for k, v in names.items() if isinstance(v, str)}}
    g["name"] = f.get("name") if isinstance(f.get("name"), str) else f["id"]
    g["ready"] = f.get("ready", True) is not False
    g["source"] = source
    return g


def _modules(vault):
    """켜진 모듈의 contributes.options — roles.py 와 같은 켜짐 규칙(ADR-035)."""
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import roles
        mods = roles.modules(on_only=True, vault=_v(vault))
    except Exception:
        return []
    out = []
    for m in mods:
        con = (m.get("json") or {}).get("contributes") if isinstance(m.get("json"), dict) else None
        opts = con.get("options") if isinstance(con, dict) else None
        if isinstance(opts, list):
            out += [(m["id"], f) for f in opts]
    return out


def declarations(vault=None, only=None, problems=None, all_devices=False):
    """선언 목록 — 코어 표 + 켜진 모듈. 선언 파일이 없거나 깨지면 None(→ 모두 high).
    only = 이 id 하나만 찾음(코어 표에 있으면 모듈을 훑지 않는다 — 훅이 턴마다 부름)."""
    reg, st = _load(registry_path(vault))
    if st != "ok" or not isinstance(reg, dict) or not schema_ok(reg.get("schema")) or not isinstance(reg.get("features"), list):
        if problems is not None:
            problems.append("선언 파일 " + {"missing": "없음", "broken": "깨짐"}.get(st, "모르는 판") + " — 모든 기능 " + NAMES["high"])
        return None
    feats, seen = [], set()
    cs = {} if all_devices else caps(vault)    # check 는 기기와 상관없이 모든 선언을 대조한다
    for src, f in [("core", f) for f in reg["features"]] + ([] if only and any(isinstance(x, dict) and x.get("id") == only for x in reg["features"]) else _modules(vault)):
        if not _valid(f):
            if problems is not None:
                problems.append("선언 꼴이 틀림(%s) — 뺌" % (f.get("id") if isinstance(f, dict) else type(f).__name__))
            continue
        if f["id"] in seen:
            if problems is not None:
                problems.append("같은 id 두 번(%s) — 처음 것만" % f["id"])
            continue
        seen.add(f["id"])
        if src == "core" and not _installed(f, vault):
            continue
        if not capable(f, cs):
            continue
        feats.append(_norm(f, src, cs))
    return [f for f in feats if f["id"] == only] if only else feats


# ── 읽기 규칙 ─────────────────────────────────────────────────────────
def default_of(f):
    """안 고른 칸의 단계 — 선언 default(그 칸 levels 안의 값)가 있으면 그것 · 없으면 high(지금 동작).
    11-21: 자동 재시작처럼 «켜면 PC 를 끄는» 칸은 새 볼트에서 끔이어야 화면(«켬»)과 동작이 같다 — 칸마다 선언한다(brain-base options.ts 와 같은 규칙)."""
    d = f.get("default")
    return d if isinstance(d, str) and d in f.get("levels", []) and d in LEVELS else "high"


def chosen(local, state, feats, problems=None):
    """고른 값(배터리 규칙 전) → {id: 단계}. 규칙 1~8."""
    if feats is None:
        return {}
    ok = state == "ok" and isinstance(local, dict) and schema_ok(local.get("schema"))
    if state == "ok" and not ok and problems is not None:
        problems.append("고른 값 파일 " + ("모르는 판" if isinstance(local, dict) else "꼴이 틀림") + " — 모든 기능 %s(파일은 그대로)" % NAMES["high"])
    if state == "broken" and problems is not None:
        problems.append("고른 값 파일 깨짐 — 모든 기능 %s(파일은 그대로)" % NAMES["high"])
    lv = local.get("levels") if ok and isinstance(local.get("levels"), dict) else {}
    out = {}
    for f in feats:
        v = lv.get(f["id"])
        good = f["ready"] and isinstance(v, str) and v in f["levels"] and v in LEVELS
        if v is not None and not good and f["ready"] and problems is not None:
            problems.append("%s 값 %r 은 고를 수 없음 — %s" % (f["id"], v, NAMES["high"]))
        out[f["id"]] = v if good else default_of(f)
    if problems is not None and ok:
        known = {f["id"] for f in feats}
        for k in lv:
            if k not in known:
                problems.append("선언에 없는 id %s — 무시(지우지 않음)" % k)
    return out


def resolve(local, state, feats, battery_now, problems=None):
    """지금 단계 → {id: 단계}. battery_now = 배터리로 도는지 묻는 함수(battery 가 lower 일 때만 부른다)."""
    out = chosen(local, state, feats, problems)
    ok = state == "ok" and isinstance(local, dict) and schema_ok(local.get("schema"))
    if ok and local.get("battery") == "lower" and any(v == "high" for v in out.values()):
        if battery_now():
            for f in feats or []:
                if out.get(f["id"]) == "high" and f["ready"] and "low" in f["levels"] and f.get("battery_keep") is not True:   # battery_keep = 배터리에서만 뜻이 있는 칸(낮추면 뜻이 바뀜)
                    out[f["id"]] = "low"
    return out


def level(fid, vault=None):
    """그 기능의 지금 단계 — 어떤 오류도 "high"(지금 동작)."""
    try:
        local, st = _load(local_path(vault))
        feats = declarations(vault, only=fid)        # 고른 값 파일이 없어도 선언 default 를 따른다(없으면 high)
        return resolve(local, st, feats, on_battery).get(fid, "high")
    except Exception:
        return "high"


def params(fid, lvl, vault=None):
    """선언의 low 숫자 등(params[단계]) — 없으면 {}."""
    try:
        feats = declarations(vault, only=fid) or []
        p = (feats[0].get("params") or {}).get(lvl) if feats else None
        return p if isinstance(p, dict) else {}
    except Exception:
        return {}


# ── 이 PC ─────────────────────────────────────────────────────────────
def _k32():
    import ctypes
    return ctypes.windll.kernel32


def power():
    """(배터리 있음, 지금 배터리로 도는지) — GetSystemPowerStatus. 모르면 (False, False)."""
    if os.name != "nt":
        return False, False
    try:
        import ctypes

        class SPS(ctypes.Structure):
            _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("pct", ctypes.c_ubyte), ("sys", ctypes.c_ubyte),
                        ("life", ctypes.c_ulong), ("full", ctypes.c_ulong)]
        s = SPS()
        if not _k32().GetSystemPowerStatus(ctypes.byref(s)):
            return False, False
        has = s.flag != 128 and s.flag != 255
        return has, has and s.ac == 0
    except Exception:
        return False, False


def on_battery():
    return power()[1]


def memory():
    """(설치 램 GB, 지금 남은 GB) — 설치 램은 GetPhysicallyInstalledSystemMemory(16GB 노트북이 15.7 로 보이지 않게)."""
    total = avail = 0.0
    if os.name == "nt":
        try:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                            ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong),
                            ("ae", ctypes.c_ulonglong)]
            m = MS()
            m.len = ctypes.sizeof(MS)
            if _k32().GlobalMemoryStatusEx(ctypes.byref(m)):
                total, avail = m.total / 2**30, m.avail / 2**30
            kb = ctypes.c_ulonglong()
            if _k32().GetPhysicallyInstalledSystemMemory(ctypes.byref(kb)) and kb.value:
                total = kb.value / 2**20
        except Exception:
            pass
    if not total:
        try:
            import psutil
            vm = psutil.virtual_memory()
            total, avail = vm.total / 2**30, vm.available / 2**30
        except Exception:
            pass
    return round(total, 1), round(avail, 2)


def machine_now():
    return {"cores": os.cpu_count() or 0, "ram_gb": memory()[0]}


def notes_count(vault=None):
    n = 0
    for d, _, fs in os.walk(os.path.join(_v(vault), "2_지식")):
        n += sum(1 for x in fs if x.endswith(".md"))
    return n


# ── 쓰기 ─────────────────────────────────────────────────────────────
def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S") + time.strftime("%z")[:3] + ":" + time.strftime("%z")[3:]


def _log(vault, rec):
    try:
        os.makedirs(out_dir(vault), exist_ok=True)
        with open(os.path.join(out_dir(vault), "log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _save(vault, via, op, mutate):
    """다시 읽고 → 바꿀 키만 고침 → 같은 폴더 임시 파일 → 이름 바꾸기 · 장부 한 줄. 깨진 파일은 덮지 않는다."""
    p = local_path(vault)
    cur, st = _load(p)
    if st == "broken" or (st == "ok" and not (isinstance(cur, dict) and schema_ok(cur.get("schema")))):
        raise OptErr("고른 값 파일이 깨졌거나 모르는 판 — `options.py reset` 으로 옆에 치운 뒤 다시")
    d = cur if st == "ok" else {"schema": SCHEMA}
    if not isinstance(d.get("levels"), dict):
        d["levels"] = {}
    before = json.loads(json.dumps(d))
    mutate(d)
    d["schema"] = SCHEMA
    if op != "migrate" or not isinstance(d.get("decided"), dict):      # 옮기기는 사람이 고른 것이 아니다 — 고른 때·곳을 그대로 둔다
        d["decided"] = {"at": _now(), "via": via}
    tmp = p + ".%d.tmp" % os.getpid()
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, p)
    ch = {k: [before["levels"].get(k), v] for k, v in d["levels"].items() if before["levels"].get(k) != v}
    ch.update({k: [v, None] for k, v in before["levels"].items() if k not in d["levels"]})   # 옮기기(migrate)가 걷은 옛 id
    rec = {"at": _now() if op == "migrate" else d["decided"]["at"], "via": via, "op": op, "levels": ch}
    if before.get("battery") != d.get("battery"):
        rec["battery"] = [before.get("battery"), d.get("battery")]
    if d.get("preset") != before.get("preset"):
        rec["preset"] = d.get("preset")
    _log(vault, rec)
    return d


def _feats_or_die(vault):
    feats = declarations(vault)
    if feats is None:
        raise OptErr("선언 파일이 없거나 깨짐 — 고를 것이 없음")
    return feats


def set_level(fid, lvl, via="cli", vault=None):
    feats = {f["id"]: f for f in _feats_or_die(vault)}
    f = feats.get(fid)
    if not f or not f["ready"]:
        raise OptErr("고를 수 있는 기능이 아님: %s" % fid)
    if lvl not in f["levels"] or lvl not in LEVELS:
        raise OptErr("%s 는 %s 만 고를 수 있음" % (f["name"], "·".join("%s(%s)" % (label(f, x), x) for x in f["levels"])))

    def m(d):
        d["levels"][fid] = lvl
        d["preset"] = "custom"
    return _save(vault, via, "set", m)


def set_battery(rule, via="cli", vault=None):
    if rule not in BATTERY:
        raise OptErr("배터리 규칙은 same · lower")
    return _save(vault, via, "battery", lambda d: d.__setitem__("battery", rule))


def latest_recommend(vault=None):
    """마지막 추천 — _index/options/recommend-*.json 중 가장 새것(없으면 고른 값 파일의 recommended)."""
    d = out_dir(vault)
    try:
        fs = sorted(x for x in os.listdir(d) if x.startswith("recommend-") and x.endswith(".json"))
    except OSError:
        fs = []
    for x in reversed(fs):
        r, st = _load(os.path.join(d, x))
        if st == "ok" and isinstance(r, dict) and isinstance(r.get("levels"), dict):
            r["file"] = os.path.join(d, x)
            return r
    loc, st = _load(local_path(vault))
    if st == "ok" and isinstance(loc, dict) and isinstance(loc.get("recommended"), dict):
        return loc["recommended"]
    return None


def preset(name, via="cli", vault=None):
    feats = [f for f in _feats_or_die(vault) if f["ready"]]
    if name == "high":
        lv = {f["id"]: "high" for f in feats}
    elif name == "min":
        lv = {f["id"]: next(x for x in LEVELS[::-1] if x in f["levels"]) for f in feats}
    elif name == "recommended":
        r = latest_recommend(vault)
        if not r:
            raise OptErr("추천이 없음 — 먼저 `options.py recommend`")
        allowed = {f["id"]: f["levels"] for f in feats}
        lv = {k: v for k, v in r["levels"].items() if k in allowed and v in allowed[k] and v in LEVELS}
    else:
        raise OptErr("프리셋은 high · recommended · min")

    def m(d):
        d["levels"].update(lv)
        d["preset"] = name
    return _save(vault, via, "preset", m)


def migrate(via="migrate", vault=None):
    """옛 칸의 고른 값을 나뉜 칸으로 옮긴다 — 선언 from {옛 id: {옛 값: 새 값}}(사용자 11-20 «각 기능별로 나눌 것»).
    새 칸에 이미 값이 있으면 그대로 · 옮긴 옛 id 가 선언에 없으면 걷는다(장부에 [옛 값, null]) · 고른 값 파일이 없거나 깨졌으면 안 씀.
    돌려줌 = {새 id: 새 값} (옮길 것이 없으면 {} 이고 파일을 안 건드림). 쓰는 명령(set·preset·apply·battery·recommend)이 먼저 부른다."""
    feats = declarations(vault)
    cur, st = _load(local_path(vault))
    if not feats or st != "ok" or not (isinstance(cur, dict) and schema_ok(cur.get("schema"))) or not isinstance(cur.get("levels"), dict):
        return {}
    have = cur["levels"]
    ids = {f["id"] for f in feats}
    put, used = {}, set()
    for f in feats:
        fr = f.get("from")
        if not isinstance(fr, dict):
            continue
        for old, mp in fr.items():
            if old in ids or old not in have or not isinstance(mp, dict):
                continue
            used.add(old)
            new = mp.get(have[old])
            if f["id"] not in have and isinstance(new, str) and new in f["levels"] and new in LEVELS:
                put[f["id"]] = new
    if not used:
        return {}

    def m(d):
        for k in used:
            d["levels"].pop(k, None)
        for k, v in put.items():
            d["levels"].setdefault(k, v)
    _save(vault, via, "migrate", m)
    return put


def reset(via="cli", vault=None):
    p = local_path(vault)
    if os.path.exists(p):
        os.replace(p, p + ".broken-" + time.strftime("%Y%m%d-%H%M%S"))
    return _save(vault, via, "reset", lambda d: None)


def apply(rec=None, overrides=None, battery=None, new_only=False, via="cli", vault=None):
    """추천을 확정해 쓴다 — levels(추천 + 사람이 고친 것) · battery · recommended · machine · decided."""
    rec = rec or latest_recommend(vault)
    if not rec:
        raise OptErr("추천이 없음 — 먼저 `options.py recommend`")
    feats = {f["id"]: f for f in _feats_or_die(vault) if f["ready"]}
    lv = {k: v for k, v in (rec.get("levels") or {}).items() if k in feats}
    for k, v in (overrides or {}).items():
        if k not in feats or v not in feats[k]["levels"] or v not in LEVELS:
            raise OptErr("고를 수 없는 값: %s=%s" % (k, v))
        lv[k] = v
    if battery is not None and battery not in BATTERY:
        raise OptErr("배터리 규칙은 same · lower")
    cur, st = _load(local_path(vault))
    have = (cur.get("levels") or {}) if st == "ok" and isinstance(cur, dict) else {}
    if new_only and st == "ok":
        lv = {k: v for k, v in lv.items() if k not in have}

    def m(d):
        d["levels"].update(lv)
        if battery is not None:
            d["battery"] = battery
        d["preset"] = "recommended" if not overrides else "custom"
        d["recommended"] = {"at": rec.get("at"), "levels": rec.get("levels"), "why": rec.get("why")}
        if rec.get("machine"):
            d["machine"] = rec["machine"]
    return _save(vault, via, "apply", m)


# ── 보기 ─────────────────────────────────────────────────────────────
def show(vault=None):
    problems = []
    feats = declarations(vault, problems=problems)
    local, st = _load(local_path(vault))
    has, bat = power()
    ch = chosen(local, st, feats, problems)
    now = resolve(local, st, feats, lambda: bat)
    ok = st == "ok" and isinstance(local, dict) and schema_ok(local.get("schema"))
    rec = latest_recommend(vault)
    saved = local.get("machine") if ok and isinstance(local.get("machine"), dict) else None
    mn = machine_now()
    changed = bool(saved) and (saved.get("cores") != mn["cores"] or abs(float(saved.get("ram_gb") or 0) - mn["ram_gb"]) >= 1)
    notes = notes_count(vault) if saved and saved.get("notes") else None
    return {
        "features": feats or [],
        "chosen": ch,
        "now": now,
        "battery": (local.get("battery") if ok and local.get("battery") in BATTERY else "same"),
        "has_battery": has,
        "on_battery": bat,
        "preset": local.get("preset") if ok else None,
        "recommend": {k: rec.get(k) for k in ("at", "levels", "why", "valid", "invalid", "battery", "battery_why", "file")} if rec else None,
        "machine": {"saved": saved, "now": mn, "changed": changed,
                    "renotes": bool(notes and saved.get("notes", 0) < 50 and notes >= 3 * saved["notes"])},
        "file": st if st != "ok" or ok else "broken",
        "problems": problems,
    }


# ── 추천: 재기 ───────────────────────────────────────────────────────
CHUNK = ("외부뇌는 옵시디언 볼트와 Claude Code 를 묶은 개인 지식 시스템이다. 세션이 시작되고 끝날 때마다 바뀐 노트를 다시 색인하고, "
         "찾기는 낱말 점수와 뜻 점수를 섞어 순위를 낸다. 노트는 머리글 단위로 잘라 40줄 창으로 나누며 노트 점수는 가장 가까운 조각의 "
         "코사인 값이다. 하옵은 재색인을 여섯 시간에 한 번으로 미루고, 사용 안 함은 낱말 찾기만 남긴다. 자동 커밋은 턴이 끝날 때마다 "
         "바뀐 것을 저장소에 남기며, 하옵은 마지막 커밋 뒤 오 분이 지난 턴 끝과 세션 끝에 몰아서 남긴다. 동시 하위 세션은 보스 세션이 "
         "큰 일을 나눠 맡기는 수이고, 로그인 출처 아침 받기는 새벽에 PC 를 깨워 크롬을 띄운 뒤 과제와 공지를 반영한다. 움직임은 기다림 표시의 "
         "회전과 반짝임이고, 시트 보기는 표 계산 엔진으로 여는 화면이다. ")


def _ref_values():
    """CPU 점수 기준(제작자 PC 1.0) — 이 파일 끝 REF_SINGLE·REF_MULTI."""
    return REF_SINGLE, REF_MULTI


def _work(stop, box, i):
    import hashlib
    import zlib
    buf = (CHUNK.encode("utf-8") * 120)[:262144]
    n = 0
    while time.perf_counter() < stop:
        hashlib.sha256(buf).digest()
        zlib.compress(buf, 6)
        n += 1
    box[i] = n


def cpu_units(secs, threads):
    """고정 일(256KB sha256 + zlib) 을 threads 개로 secs 초 → 초당 단위. 둘 다 GIL 을 놓아 코어 수만큼 는다."""
    import threading
    box = [0] * threads
    stop = time.perf_counter() + secs
    ts = [threading.Thread(target=_work, args=(stop, box, i), daemon=True) for i in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return sum(box) / secs


def _cpu_busy(secs):
    """secs 초 동안 CPU 평균 사용률(%) — GetSystemTimes · 모르면 None."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        FT = ctypes.c_ulonglong

        def st():
            i, k, u = FT(), FT(), FT()
            _k32().GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
            return i.value, k.value + u.value
        i0, t0 = st()
        time.sleep(secs)
        i1, t1 = st()
        return round(100.0 * (1 - (i1 - i0) / max(1, t1 - t0)), 1)
    except Exception:
        return None


def _clocks():
    """(잠듦을 포함한 ms, 잠듦을 뺀 ms) — 차이가 커지면 그 사이 잠들었다."""
    if os.name != "nt":
        return time.time() * 1000, time.monotonic() * 1000
    import ctypes
    u = ctypes.c_ulonglong()
    _k32().QueryUnbiasedInterruptTime(ctypes.byref(u))
    _k32().GetTickCount64.restype = ctypes.c_ulonglong
    return float(_k32().GetTickCount64()), u.value / 10000.0


def _ps(cmd, timeout=20):
    import subprocess
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True,
                           timeout=timeout, creationflags=NOWIN)
        return r.stdout.decode("utf-8", "replace").strip()
    except Exception:
        return ""


def gpu():
    """(이름, 외장인지) — nvidia-smi → 없으면 WMI. 모르면 ("", False)."""
    import subprocess
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True,
                           timeout=10, creationflags=NOWIN)
        line = r.stdout.decode("utf-8", "replace").strip().splitlines()
        if r.returncode == 0 and line:
            return line[0].split(",")[0].strip(), True
    except Exception:
        pass
    names = [x.strip() for x in _ps("[Console]::OutputEncoding=[Text.Encoding]::UTF8; (Get-CimInstance Win32_VideoController).Name").splitlines() if x.strip()]
    disc = [n for n in names if re.search(r"NVIDIA|GeForce|Quadro|Radeon RX|Radeon Pro|Arc A\d", n, re.I)]
    real = [n for n in names if not re.search(r"Basic Display|Remote|Virtual|Parsec|Meta", n, re.I)]
    return ((disc or real or [""])[0], bool(disc))


def anim_on():
    """윈도 «애니메이션 효과» — SPI_GETCLIENTAREAANIMATION. 모르면 True."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        b = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(b), 0)
        return bool(b.value)
    except Exception:
        return True


def disk_kind(vault):
    """볼트 드라이브의 SSD·HDD — Get-PhysicalDisk · 모르면 ""."""
    drv = os.path.splitdrive(os.path.abspath(_v(vault)))[0].rstrip(":")
    if not drv:
        return ""
    out = _ps("$n=(Get-Partition -DriveLetter %s -ErrorAction Stop).DiskNumber; (Get-PhysicalDisk | Where-Object DeviceId -eq \"$n\").MediaType" % drv)
    return {"SSD": "SSD", "HDD": "HDD"}.get(out.strip().splitlines()[-1].strip() if out.strip() else "", "")


def disk_probe(vault):
    """볼트 밖 같은 드라이브 임시 폴더에 작은 파일 1,000개 쓰고 지움 + 64MB 쓰기·읽기 → (작은 파일 초, MB/초)."""
    import shutil
    import tempfile
    vd = os.path.splitdrive(os.path.abspath(_v(vault)))[0].lower()
    base = tempfile.gettempdir()
    if os.path.splitdrive(base)[0].lower() != vd:
        base = os.path.dirname(os.path.abspath(_v(vault)))
    d = tempfile.mkdtemp(prefix="brain-optprobe-", dir=base)
    try:
        small = b"x" * 1024
        t0 = time.perf_counter()
        for i in range(1000):
            with open(os.path.join(d, "%d.md" % i), "wb") as f:
                f.write(small)
        for i in range(1000):
            os.remove(os.path.join(d, "%d.md" % i))
        t_small = time.perf_counter() - t0
        blob = os.urandom(1 << 20)
        big = os.path.join(d, "big.bin")
        t0 = time.perf_counter()
        with open(big, "wb") as f:
            for _ in range(64):
                f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        with open(big, "rb") as f:
            while f.read(1 << 22):
                pass
        mbps = 128 / max(1e-6, time.perf_counter() - t0)
        return round(t_small, 2), round(mbps)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def git_status_secs(vault):
    import subprocess
    t0 = time.perf_counter()
    try:
        r = subprocess.run(["git", "-C", _v(vault), "--no-optional-locks", "status", "--porcelain", "--untracked-files=normal"],
                           capture_output=True, timeout=60, creationflags=NOWIN)
        return round(time.perf_counter() - t0, 2) if r.returncode == 0 else None
    except Exception:
        return None


def probe_embed_child():
    """(자식) 지금 모델로 10청크 — 줄마다 «load 초» · «chunk i 초» · 모델이 없으면 «nomodel» · 안 돌면 «fail 까닭»."""
    sys.path.insert(0, SYS)
    try:
        import search
        name = search.config_model_name()
        if not search._hf_snapshot(name):
            print("nomodel", flush=True)
            return
        t0 = time.perf_counter()
        enc = search._encoder(name, 10)
        print("load %.3f" % (time.perf_counter() - t0), flush=True)
        for i in range(10):
            text = search.pdoc(name, CHUNK[i * 37:] + CHUNK[:i * 37])
            enc.encode([text], normalize_embeddings=True, show_progress_bar=False, batch_size=32)
            print("chunk %d %.3f" % (i + 1, time.perf_counter() - t0), flush=True)
    except Exception as e:
        print("fail %s: %s" % (type(e).__name__, str(e)[:120]), flush=True)


def embed_probe(limit=40.0):
    """10청크 시간(적재 포함) — 40초를 넘으면 멈추고 끝낸 청크 값으로 미룸. → (초 또는 None, 상태)."""
    import subprocess
    import threading
    p = subprocess.Popen([sys.executable, "-u", os.path.abspath(__file__), "_probe-embed"], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, creationflags=NOWIN)
    lines = []
    th = threading.Thread(target=lambda: [lines.append(x.decode("utf-8", "replace").strip()) for x in p.stdout], daemon=True)
    th.start()
    th.join(limit)
    if p.poll() is None:
        p.kill()
    th.join(2)
    if any(x == "nomodel" for x in lines):
        return None, "nomodel"
    fail = [x for x in lines if x.startswith("fail")]
    if fail:
        return None, fail[0]
    load = next((float(x.split()[1]) for x in lines if x.startswith("load ")), None)
    ch = [(int(x.split()[1]), float(x.split()[2])) for x in lines if x.startswith("chunk ")]
    if ch and ch[-1][0] == 10:
        return round(ch[-1][1], 1), "ok"
    if ch and load is not None:
        per = (ch[-1][1] - load) / ch[-1][0]
        return round(load + per * 10, 1), "cut"        # 40초에 멈춤 — 끝낸 청크로 미룸
    return None, "slow" if load is None else "cut-load"


def measure(vault=None, log=None):
    """§4-1 — 60~90초. 볼트 안에는 쓰지 않는다."""
    say = log or (lambda s: None)
    m = {"at": _now()}
    tick0, unb0 = _clocks()
    has, bat = power()
    m["battery"], m["on_battery"] = has, bat
    say("CPU 쉬는 정도 10초")
    m["busy_before"] = _cpu_busy(10)
    ram_min = [memory()[1]]
    stop = [False]

    def sample():
        while not stop[0]:
            ram_min.append(memory()[1])
            time.sleep(1)
    import threading
    th = threading.Thread(target=sample, daemon=True)
    th.start()
    try:
        m["cores"] = os.cpu_count() or 0
        m["ram_gb"], _ = memory()
        say("GPU · 디스크 종류 · 애니메이션")
        m["gpu"], m["gpu_discrete"] = gpu()
        m["disk"] = disk_kind(vault)
        m["anim"] = anim_on()
        try:
            import shutil
            m["disk_free_gb"] = round(shutil.disk_usage(_v(vault)).free / 2**30, 1)
        except OSError:
            m["disk_free_gb"] = None
        say("CPU 점수 10초")
        rs, rm = _ref_values()
        s1 = cpu_units(5, 1)
        sn = cpu_units(5, max(1, m["cores"]))
        m["cpu_units"] = [round(s1, 1), round(sn, 1)]
        m["cpu_score"] = round(((s1 / rs) * (sn / rm)) ** 0.5, 2) if rs and rm else None
        say("디스크 속도")
        m["disk_small_s"], m["disk_mbps"] = disk_probe(vault)
        say("git status")
        m["git_status_s"] = git_status_secs(vault)
        m["notes"] = notes_count(vault)
        say("임베딩 10청크(40초 안)")
        m["embed10_s"], m["embed_state"] = embed_probe()
    finally:
        stop[0] = True
        th.join(2)
    m["ram_min_gb"] = round(min(ram_min), 2)
    tick1, unb1 = _clocks()
    m["slept_s"] = round(max(0.0, ((tick1 - tick0) - (unb1 - unb0)) / 1000), 1)
    m["secs"] = round((tick1 - tick0) / 1000, 1)
    return m


# ── 추천: 규칙(§4-2) ─────────────────────────────────────────────────
def _r_search(m):
    if m.get("embed_state", "").startswith("fail"):
        return "off", "모델이 안 돎(%s)" % m["embed_state"][5:60]
    e10 = m.get("embed10_s")
    est = "잰"
    if e10 is None and m.get("cpu_score"):
        e10, est = 18.9 / m["cpu_score"], "CPU 점수로 미룬"
    if m.get("disk_free_gb") is not None and m["disk_free_gb"] < 2:
        return "off", "디스크 남은 %.1fGB" % m["disk_free_gb"]
    if m["ram_min_gb"] < 1.0:
        return "off", "남은 램 최저 %.1fGB" % m["ram_min_gb"]
    if e10 is None:
        return "low", "임베딩을 못 잼 · 남은 램 %.1fGB" % m["ram_min_gb"]
    t50 = e10 * 2.4
    why = "바뀐 50청크 예상 %.0f초(%s) · 남은 램 %.1fGB" % (t50, est, m["ram_min_gb"])
    return ("high" if t50 <= 90 and m["ram_min_gb"] >= 1.5 else "low"), why


def _r_git(m):
    g = m.get("git_status_s")
    kind = m.get("disk") or ("SSD 추정" if m.get("disk_small_s") is not None and m["disk_small_s"] < 3 else "")
    ssd = kind.startswith("SSD")
    why = "git status %s · %s" % ("%.1f초" % g if g is not None else "못 잼", kind or "디스크 모름")
    return ("high" if g is not None and g <= 0.5 and ssd else "low"), why


def _r_sessions(m):
    return ("high" if m["ram_gb"] >= 16 else "low"), "램 %.0fGB · 세션 하나 0.45~0.6GB" % m["ram_gb"]


def _r_browser_wake(m):
    return ("high" if m["ram_gb"] > 8 else "low"), "램 %.0fGB · 크롬 25분이 아침 사용과 겹침" % m["ram_gb"]


def _r_motion(m):
    if not m.get("anim", True):
        return "low", "윈도 애니메이션 효과 꺼짐"
    s = m.get("cpu_score")
    why = "%s GPU · CPU 점수 %s" % ("외장" if m.get("gpu_discrete") else "내장", "%.1f" % s if s is not None else "못 잼")
    return ("high" if m.get("gpu_discrete") or (s is not None and s >= 0.6) else "low"), why


def _r_sheet(m):
    s = m.get("cpu_score") or 0
    why = "램 %.0fGB · 첫 열기 예상 %s" % (m["ram_gb"], "%.0f초" % (3.7 / s) if s else "못 잼")
    return ("high" if m["ram_gb"] >= 12 and s >= 0.5 else "low"), why


def _on(rule):
    """켬/끔 칸(levels high·off)의 규칙 — 옛 단계 규칙이 «낮음»이면 «끔»(옛 낮음 = 그 동작을 안 함 · 11-20 나눔)."""
    def r(m):
        x, w = rule(m)
        return ("high" if x == "high" else "off"), w
    return r


def wake_timers():
    """전원 구성표 «절전 모드 해제 타이머 허용»(RTCWAKE) — (전원 연결, 배터리) 색인 0 사용 안 함 · 1 사용 · 2 중요만 · 못 읽으면 (None, None)."""
    import subprocess
    try:
        r = subprocess.run(["powercfg", "/q", "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE"], capture_output=True, timeout=10, creationflags=NOWIN)
        v = re.findall(rb"0x([0-9a-fA-F]{8})\s*$", r.stdout, re.M)[-2:]
        return tuple(int(x, 16) for x in v) if len(v) == 2 else (None, None)
    except Exception:
        return None, None


def _r_wake_pc(m):
    """PC 깨우기 — 켜 두어도 전원 구성표가 막으면 윈도가 안 깨운다(해가 없음) · 까닭에 지금 허용을 적는다."""
    ac, dc = m["wake_timers"] if "wake_timers" in m else wake_timers()
    w = {0: "사용 안 함", 1: "사용", 2: "중요만"}
    return "high", "깨우기 타이머 전원 연결 %s · 배터리 %s" % (w.get(ac, "못 잼"), w.get(dc, "못 잼"))


def _r_search_on(m):
    """뜻 찾기·의미 링크 — 모델·램·디스크로 돌 수 없을 때만 끔(재색인이 느린 것은 «재색인 빈도» 몫)."""
    x, w = _r_search(m)
    return ("off" if x == "off" else "high"), w


def _r_reclaim(m):
    # 되찾기 규칙(proc.reclaim.*)은 남은 프로세스를 끄는 일이라 사양이 낮을수록 더 필요하다 — 늘 켬을 추천(끄기는 사람 몫)
    return "high", "램 %.0fGB · 남은 시험·배경 프로세스를 10분마다 치움" % m["ram_gb"]


RULES = {"search": _r_search, "search_on": _r_search_on, "git": _r_git, "sessions": _r_sessions, "browser_wake": _r_browser_wake,
         "browser_on": _on(_r_browser_wake), "wake_pc": _r_wake_pc, "motion": _r_motion, "motion_on": _on(_r_motion), "sheet": _r_sheet, "reclaim": _r_reclaim}


def decide(m, feats):
    """재 값 → 기능마다 (단계, 까닭). 높음·낮음·끔 칸에서 추천은 «끔»(off)을 스스로 고르지 않는다 — 돌 수 없을 때(램·디스크·모델)만.
    켬/끔 칸(levels high·off)은 «끔»이 옛 «낮음» 자리다(규칙 이름 *_on)."""
    lv, why = {}, {}
    empty = m.get("notes", 0) < 50
    for f in feats:
        rule = RULES.get(f.get("recommend") or "")
        if f.get("recommend") == "default":       # 재서 가를 것이 없는 칸(예 자체 절전 · 장치 유무는 needs 가 이미 거름) — 선언 기본값(high)과 그 까닭
            rule = lambda _m, f=f: (default_of(f), f.get("default_why") or "기본값")  # noqa: E731
        if not f["ready"] or not rule:
            continue
        x, w = rule(m)
        if x not in f["levels"]:
            x = "low" if "low" in f["levels"] else "high"
        if empty and f.get("recommend") in ("search", "git"):
            w += " · 빈 볼트 값"
        lv[f["id"]], why[f["id"]] = x, w
    return lv, why


def probe_modules(vault=None, log=None):
    """켜진 모듈의 contributes.probe(이 기기 장치 재기 · device.json 을 씀)를 돌린다 — 추천이 이 기기 기준으로 칸을 거르게.
    명령 꼴 = ["{py}", "<볼트 상대 .py>", 인자...] 만(그 밖은 건너뜀) · 하나 60초 · 실패는 건너뜀(그 장치는 «모름» = 칸을 숨기지 않음)."""
    import subprocess
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import roles
        mods = roles.modules(on_only=True, vault=_v(vault))
    except Exception:
        return []
    done = []
    for m in mods:
        con = (m.get("json") or {}).get("contributes") if isinstance(m.get("json"), dict) else None
        cmd = con.get("probe") if isinstance(con, dict) else None
        if not (isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "{py}" and all(isinstance(x, str) for x in cmd)
                and cmd[1].endswith(".py") and not os.path.isabs(cmd[1]) and ".." not in cmd[1].replace("\\", "/").split("/")):
            continue
        if log:
            log("이 기기 재기: %s" % m["id"])
        try:
            r = subprocess.run([sys.executable, os.path.join(_v(vault), cmd[1])] + cmd[2:], capture_output=True, timeout=60,
                               creationflags=NOWIN, cwd=_v(vault))
            done.append((m["id"], r.returncode))
        except Exception:
            done.append((m["id"], None))
    return done


def recommend(vault=None, new_only=False, log=None):
    probe_modules(vault, log)
    feats = [f for f in (declarations(vault) or []) if f["ready"]]
    local, st = _load(local_path(vault))
    have = set((local.get("levels") or {}).keys()) | set(((local.get("recommended") or {}).get("levels") or {}).keys()) \
        if st == "ok" and isinstance(local, dict) else set()
    if new_only and st == "ok":
        feats = [f for f in feats if f["id"] not in have]
        if not feats:
            return {"schema": SCHEMA, "at": _now(), "levels": {}, "why": {}, "new_only": True, "skipped": "새 기능 없음"}
    m = measure(vault, log)
    lv, why = decide(m, feats)
    invalid = []
    if m["on_battery"]:
        invalid.append("배터리로 잼 — 전원 연결 뒤 다시")
    if m["slept_s"] > 2:
        invalid.append("재는 사이 %.0f초 잠듦" % m["slept_s"])
    rec = {"schema": SCHEMA, "at": m["at"], "valid": not invalid, "invalid": invalid, "levels": lv, "why": why,
           "battery": "lower" if m["battery"] else "same", "battery_why": "배터리 있는 PC" if m["battery"] else "배터리 없음",
           "machine": {"cores": m["cores"], "ram_gb": m["ram_gb"], "gpu": m["gpu"], "gpu_discrete": m["gpu_discrete"],
                       "disk": m["disk"], "battery": m["battery"], "cpu_score": m["cpu_score"], "notes": m["notes"]},
           "measured": m, "new_only": bool(new_only and st == "ok")}
    if (m.get("busy_before") or 0) > 50:
        rec["note"] = "재기 전 CPU %.0f%% — 다른 일이 돌던 중" % m["busy_before"]
    os.makedirs(out_dir(vault), exist_ok=True)
    p = os.path.join(out_dir(vault), "recommend-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    rec["file"] = p
    return rec


def table(rec, vault=None):
    """사람이 읽는 표 — 지금과 다른 줄을 앞에."""
    if rec.get("skipped"):
        return "옵션 추천: %s(재지 않음)" % rec["skipped"]
    feats = {f["id"]: f for f in (declarations(vault) or [])}
    s = show(vault)
    m = rec.get("measured") or {}
    head = "옵션 추천 (%s · %s초 · %s)" % (rec["at"][5:16].replace("T", " "), m.get("secs", "?"),
                                       "유효" if rec.get("valid") else "무효: " + " · ".join(rec.get("invalid") or []))
    pc = "이 PC: 논리 %s코어 · 램 %sGB(재는 동안 남은 최저 %sGB) · GPU %s(%s) · %s · 배터리 %s · CPU 점수 %s" % (
        m.get("cores"), m.get("ram_gb"), m.get("ram_min_gb"), m.get("gpu") or "모름", "외장" if m.get("gpu_discrete") else "내장",
        m.get("disk") or "디스크 종류 모름", "있음" if m.get("battery") else "없음", m.get("cpu_score"))
    rows = []
    for k, v in rec["levels"].items():
        cur = s["chosen"].get(k, "high")
        if k not in feats:              # 옛 추천 파일의 옛 id(나뉘기 전) — 표에 안 올림
            continue
        rows.append((cur == v, feats[k].get("name", k), label(feats[k], cur), label(feats[k], v), rec["why"].get(k, "")))
    rows.sort(key=lambda r: r[0])
    out = [head, pc, "", "| 기능 | 지금 | 추천 | 까닭 |", "|---|---|---|---|"]
    out += ["| %s | %s | %s | %s |" % r[1:] for r in rows]
    bn = {"same": "바꾸지 않음", "lower": "배터리일 때 낮춤"}
    out.append("| 배터리 규칙 | %s | %s | %s |" % (bn[s["battery"]], bn[rec["battery"]], rec["battery_why"]))
    if rec.get("note"):
        out.append("\n" + rec["note"])
    return "\n".join(out)


# ── 대조(§6 5·6) ────────────────────────────────────────────────────
SAFETY = ["3_시스템/hooks/core-gate.ps1", "3_시스템/hooks/core-gate-decide.ps1", "3_시스템/hooks/core-gate-front.py",
          "3_시스템/hooks/pre-commit", "3_시스템/hooks/ops-guard.ps1"]
READ_RX = re.compile(r"""(?:options\.level|Get-OptionLevel\s+\S+)\s*\(?\s*["']([a-z][a-z0-9_.-]+)["']""")


def check(vault=None):
    """선언된 id 마다 owner 에 그 id 를 읽는 부름이 있고 · 코드가 부르는 id 는 모두 선언에 있고 · 안전 파일은 옵션을 안 읽는다."""
    v = _v(vault)
    bad, ok = [], []
    problems = []
    feats = declarations(vault, problems=problems, all_devices=True)
    if feats is None:
        return {"ok": False, "bad": problems, "good": []}
    ids = {f["id"] for f in feats}
    for f in feats:
        if "default" in f and default_of(f) != f.get("default"):
            bad.append("%s: default %r 는 그 칸 levels 에 없음 — high 로 읽음" % (f["id"], f.get("default")))
        if not f["ready"]:
            ok.append("%s: ready false — 대조 안 함" % f["id"])
            continue
        for o in f.get("owner") or []:
            p = os.path.join(v, o)
            try:
                if os.path.isdir(p):        # 주인이 폴더(조리법 묶음) — 그 안 파일 중 하나라도 id 를 적으면 읽는 쪽
                    t = "\n".join(open(os.path.join(p, x), encoding="utf-8", errors="replace").read()
                                  for x in sorted(os.listdir(p)) if os.path.isfile(os.path.join(p, x)))
                else:
                    t = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                bad.append("%s: owner 없음 %s" % (f["id"], o))
                continue
            (ok if ('"%s"' % f["id"] in t or "'%s'" % f["id"] in t) else bad).append("%s: %s" % (f["id"], o))
    for root in ("3_시스템", ".claude/skills"):
        for d, dirs, fs in os.walk(os.path.join(v, root)):
            dirs[:] = [x for x in dirs if not x.startswith(("_index", "__pycache__", ".", "_ref", "_claude-memory", "_eval"))]
            for x in fs:
                if not x.endswith((".py", ".ps1")) or x == "options.py":
                    continue
                try:
                    t = open(os.path.join(d, x), encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for i in READ_RX.findall(t):
                    if i not in ids:
                        bad.append("선언에 없는 id 를 읽음: %s (%s)" % (i, os.path.relpath(os.path.join(d, x), v)))
    for s in SAFETY:
        try:
            t = open(os.path.join(v, s), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        hit = [w for w in ("options.local", "options.level", "Get-OptionLevel", "import options", "options.registry") if w in t]
        (bad if hit else ok).append("안전 %s: %s" % (s, "옵션을 읽음 " + ",".join(hit) if hit else "옵션 안 읽음"))
    return {"ok": not bad, "bad": problems + bad, "good": ok}


# ── CLI ──────────────────────────────────────────────────────────────
def main(argv=None):
    import argparse
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_probe-embed"]:
        return probe_embed_child()
    ap = argparse.ArgumentParser(prog="options.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get")
    g.add_argument("id")
    sh = sub.add_parser("show")
    sh.add_argument("--json", action="store_true")
    for name, args in (("set", ("id", "level")), ("battery", ("rule",)), ("preset", ("name",)), ("reset", ())):
        p = sub.add_parser(name)
        for a in args:
            p.add_argument(a)
        p.add_argument("--via", default="cli")
        p.add_argument("--json", action="store_true")
    r = sub.add_parser("recommend")
    r.add_argument("--new-only", action="store_true")
    r.add_argument("--json", action="store_true")
    a2 = sub.add_parser("apply")
    a2.add_argument("--file")
    a2.add_argument("--set", action="append", default=[])
    a2.add_argument("--battery", choices=BATTERY)
    a2.add_argument("--new-only", action="store_true")
    a2.add_argument("--via", default="cli")
    a2.add_argument("--json", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("--json", action="store_true")
    mg = sub.add_parser("migrate")
    mg.add_argument("--via", default="migrate")
    mg.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd in ("set", "battery", "preset", "apply", "recommend"):
            migrate(via="migrate:" + getattr(a, "via", a.cmd))    # 나뉜 칸으로 옛 값을 먼저 옮긴다(새 칸을 «새 기능»으로 재거나 덮지 않게)
        if a.cmd == "migrate":
            put = migrate(via=a.via)
            print(json.dumps({"ok": True, "moved": put}, ensure_ascii=False) if a.json else ("옮김: " + " · ".join("%s=%s" % kv for kv in put.items()) if put else "옮길 옛 값 없음"))
        elif a.cmd == "get":
            print(level(a.id))
        elif a.cmd == "show":
            s = show()
            print(json.dumps(s, ensure_ascii=False) if a.json else "\n".join(
                ["%s: %s%s" % (f["name"], label(f, s["now"].get(f["id"], "high")), "" if f["ready"] else " (아직 없음)") for f in s["features"]]
                + ["배터리 규칙: %s" % s["battery"]] + ["⚠ " + p for p in s["problems"]]))
        elif a.cmd in ("set", "battery", "preset", "reset"):
            d = {"set": lambda: set_level(a.id, a.level, a.via), "battery": lambda: set_battery(a.rule, a.via),
                 "preset": lambda: preset(a.name, a.via), "reset": lambda: reset(a.via)}[a.cmd]()
            print(json.dumps({"ok": True, "levels": d.get("levels"), "battery": d.get("battery"), "preset": d.get("preset")}, ensure_ascii=False))
        elif a.cmd == "recommend":
            rec = recommend(new_only=a.new_only, log=None if a.json else (lambda t: print("· " + t, file=sys.stderr, flush=True)))
            print(json.dumps({k: v for k, v in rec.items() if k != "measured"} | {"measured": rec.get("measured")}, ensure_ascii=False)
                  if a.json else table(rec))
        elif a.cmd == "apply":
            rec = None
            if a.file:
                rec, st = _load(a.file)
                if st != "ok":
                    raise OptErr("추천 파일을 못 읽음: " + a.file)
            ov = dict(x.split("=", 1) for x in a.set)
            d = apply(rec, ov, a.battery, a.new_only, a.via)
            print(json.dumps({"ok": True, "levels": d.get("levels"), "battery": d.get("battery"), "preset": d.get("preset")}, ensure_ascii=False))
        elif a.cmd == "check":
            r = check()
            print(json.dumps(r, ensure_ascii=False) if a.json else "\n".join(["✓ " + x for x in r["good"]] + ["✗ " + x for x in r["bad"]]))
            return 0 if r["ok"] else 1
    except OptErr as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False) if getattr(a, "json", False) else "✗ " + str(e))
        return 2
    return 0


# CPU 점수 기준값 — 제작자 PC(논리 16코어 · 전원 연결)에서 cpu_units(5, 1) · cpu_units(5, 16) 를 잰 값.
# 2026-11-07 00:03 KST 세 번의 가운데(한 코어 1396.6·1510.8·1471.8 · 모든 코어 10069.8·11175.8·10374.2 · 재기 전 CPU 15%).
REF_SINGLE = 1471.8
REF_MULTI = 10374.2

if __name__ == "__main__":
    sys.exit(main())
