"""초안 비교 한 장 — 사용자에게 화면·노트 꼴 초안을 보여 주는 하나뿐인 방식.

    py -3 3_시스템/draft.py new <폴더> [안 수=3]   뼈대(초안.json · A.html …)
    py -3 3_시스템/draft.py build <폴더> [--dark]   비교.html + 비교.png(+ 비교-어둠.png) + 원칙 검사
    py -3 3_시스템/draft.py icon <낱말>             옵시디언 아이콘 이름 찾기

폴더 = <작업 폴더>/초안/<n>차. 안 하나 = <id>.html 하나:
    <style>이 안만의 꼴 · 색은 var(--…) 만</style>
    <section data-frame="첫 화면"> … </section>
    <section data-frame="연필 누른 뒤"> … </section>
  자료(노트 이름·값)는 data-d 를 단 요소에 · 아이콘은 <i data-icon="clock"></i> · 마우스 올린 꼴은 class="is-hover".
  지금 화면을 바꾸는 일이면 지금.html(같은 꼴)을 두면 맨 앞 칸에 «지금»으로 붙는다.
초안.json = {"제목","할 일","합격선":[…],"폭":360,"안":[{"id":"A","이름","이점","손해","추천":true}],"까닭"}.
원칙·절차 = 스킬 draft(볼트에 디자인 원칙 노트가 있으면 그것도).
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
HERE = VAULT / "3_시스템" / "draft"
ICON_CACHE = VAULT / "3_시스템" / "_index" / "draft-icons.json"
MAX_W = 1800      # 나란히 놓을 수 있는 쪽 너비(px). 넘으면 세로로 쌓는다
NOWIN = 0x08000000  # CREATE_NO_WINDOW — 창을 띄우지 않는다(사용자 창 앞을 안 뺏음)

sys.stdout.reconfigure(encoding="utf-8")


# ── 아이콘: 설치된 옵시디언 번들의 lucide 표를 그대로 쓴다(setIcon 과 같은 이름·같은 별칭) ──
def _asar() -> Path | None:
    cands = sorted(Path(os.environ.get("APPDATA", "")).glob("obsidian/obsidian-*.asar"), key=lambda p: p.stat().st_mtime)
    cands += [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Obsidian/resources/obsidian.asar"]
    real = [p for p in cands if p.exists()]
    return real[-1] if real else None


def _js_obj(js: str, anchor: str) -> dict:
    i = js.find(anchor)
    if i < 0:
        return {}
    i = js.rfind("{", 0, i)
    depth, j, q = 0, i, None
    while j < len(js):
        c = js[j]
        if q:
            if c == "\\":
                j += 1
            elif c == q:
                q = None
        elif c in "\"'`":
            q = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    s = js[i:j + 1]
    s = re.sub(r'([{,\[])\s*([A-Za-z_$][\w$]*)\s*:', r'\1"\2":', s)
    s = s.replace("!0", "1").replace("!1", "0")
    s = re.sub(r"([,\[])(-?)\.(\d)", r"\g<1>\g<2>0.\3", s)  # .5 → 0.5(JS 숫자 → JSON)
    return json.loads(s)


def icons() -> dict:
    src = _asar()
    if ICON_CACHE.exists():
        cache = json.loads(ICON_CACHE.read_text("utf-8"))
        if not src or cache.get("src") == f"{src.name}:{int(src.stat().st_mtime)}":
            return cache
    if not src:
        return {"table": {}, "alias": {}}
    import struct
    with open(src, "rb") as h:
        head = h.read(16)
        hsize, jlen = struct.unpack("<I", head[4:8])[0], struct.unpack("<I", head[12:16])[0]
        hdr = json.loads(h.read(jlen).decode("utf-8"))
        v = hdr["files"]["app.js"]
        h.seek(8 + hsize + int(v["offset"]))
        js = h.read(v["size"]).decode("utf-8", "replace")
    cache = {"src": f"{src.name}:{int(src.stat().st_mtime)}",
             "table": _js_obj(js, '"a-arrow-down":[['), "alias": _js_obj(js, '"create-new":"edit"')}
    ICON_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ICON_CACHE.write_text(json.dumps(cache, ensure_ascii=False), "utf-8")
    return cache


def svg(name: str, ic: dict) -> str:
    t, a = ic["table"], ic["alias"]
    key = name[7:] if name.startswith("lucide-") else a.get(name, name)
    parts = t.get(key)
    if parts is None:
        return f'<span class="svg-icon" title="아이콘 없음 {html.escape(name)}">?</span>'
    out = []
    for p in parts:
        k = p[0]
        if k == 0:
            out.append(f'<line x1="{p[1]}" y1="{p[2]}" x2="{p[3]}" y2="{p[4]}"/>')
        elif k == 1:
            out.append(f'<circle cx="{p[1]}" cy="{p[2]}" r="{p[3]}"{" fill=\"currentColor\"" if len(p) > 4 and p[4] else ""}/>')
        elif k == 2:
            out.append(f'<polyline points="{p[1]}"/>')
        elif k == 3:
            out.append(f'<polygon points="{p[1]}"/>')
        elif k == 4:
            out.append(f'<ellipse cx="{p[1]}" cy="{p[2]}" rx="{p[3]}" ry="{p[4]}"/>')
        elif k == 5:
            ex = "".join(f' {n}="{p[i]}"' for i, n in ((5, "rx"), (6, "ry"), (7, "transform")) if len(p) > i and p[i])
            out.append(f'<rect x="{p[1]}" y="{p[2]}" width="{p[3]}" height="{p[4]}"{ex}/>')
        elif k == 6:
            out.append(f'<path d="{p[1]}"{" fill=\"currentColor\"" if len(p) > 2 and p[2] else ""}/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="svg-icon lucide-{key}">' + "".join(out) + "</svg>")


# ── 안 파일 읽기 ──
def frames(text: str, ic: dict) -> tuple[str, list[tuple[str, str]]]:
    text = re.sub(r'<i\s+data-icon="([^"]+)"\s*(?:class="([^"]*)")?\s*>\s*</i>',
                  lambda m: svg(m.group(1), ic).replace('class="svg-icon', f'class="svg-icon {m.group(2) or ""}'.rstrip()), text)
    own = "\n".join(re.findall(r"<style[^>]*>([\s\S]*?)</style>", text))
    out, pos = [], 0
    while (m := re.compile(r'<section\s+data-frame="([^"]*)"[^>]*>').search(text, pos)):
        depth, j = 1, m.end()
        for t in re.finditer(r"<(/?)section\b", text[m.end():]):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                j = m.end() + t.start()
                break
        out.append((m.group(1), text[m.end():j]))
        pos = j
    return own, out


def doc(own: str, body: str, fid: str, theme: str, check: str, css: str) -> str:
    return ("<!doctype html><html data-theme=\"" + theme + "\"><head><meta charset=\"utf-8\"><style>" + css + "</style>"
            "<style data-own>" + own + "</style></head><body>" + body + "<script>window.__frame=" + json.dumps(fid) + ";" + check + "</script></body></html>")


PAGE = r"""<!doctype html><html lang="ko" data-theme="light"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>__THEME__
html,body{background:var(--background-secondary)}
.pg{padding:20px 24px 24px;width:max-content}
.hd{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:16px;max-width:var(--pw)}
.hd h1{margin:0;font-size:var(--font-ui-large);font-weight:var(--font-semibold)}
.hd .do{color:var(--text-muted);font-size:var(--font-ui-medium)}
.hd .pass{display:flex;gap:6px;flex-wrap:wrap}
.grid{display:grid;column-gap:24px;row-gap:8px;align-items:start}
.ch{display:flex;align-items:center;gap:8px;padding-bottom:2px}
.ch .k{font-size:var(--font-ui-large);font-weight:var(--font-semibold)}
.ch .n{font-size:var(--font-ui-medium);color:var(--text-muted)}
.ch .rec{color:var(--text-accent);font-size:var(--font-ui-medium)}
.cell .cap{font-size:var(--font-ui-smaller);color:var(--text-faint);margin:6px 0 4px}
.cell iframe{display:block;border:1px solid var(--background-modifier-border);border-radius:var(--radius-m);background:var(--background-primary);height:60px}
.ft{font-size:var(--font-ui-small);display:flex;flex-direction:column;gap:2px;padding-top:6px}
.ft .p{color:var(--text-normal)} .ft .m{color:var(--text-muted)} .ft .c{color:var(--text-faint);font-size:var(--font-ui-smaller)}
.ft .c.bad{color:var(--text-warning)}
.why{margin-top:16px;font-size:var(--font-ui-small);color:var(--text-muted);max-width:var(--pw)}
.why b{color:var(--text-accent);font-weight:normal}
.tg{position:fixed;top:12px;right:12px}
.shot .tg{display:none}
</style></head><body><div class="pg" style="--pw:__PW__px">
<div class="hd"><h1>__TITLE__</h1><span class="do">__DO__</span><span class="pass">__PASS__</span></div>
<div class="grid" style="grid-template-columns:__COLS__">__CELLS__</div>
__WHY__
</div>
<button class="ib tg" aria-label="밝기" onclick="flip()">__SUN__</button>
<pre id="결과" hidden></pre>
<script>
const FR=__FRAMES__, CK=__CHECKS__, N=Object.keys(FR).length, got={};
const q=new URLSearchParams(location.search), TH=q.get("theme")||"light";
document.documentElement.dataset.theme=TH; if(q.has("shot"))document.body.classList.add("shot");
for(const [id,src] of Object.entries(FR)){const f=document.querySelector(`iframe[data-id="${id}"]`);f.srcdoc=src.replace('data-theme="light"',`data-theme="${TH}"`);}
function flip(){const v=document.documentElement.dataset.theme==="dark"?"light":"dark";document.documentElement.dataset.theme=v;for(const f of document.querySelectorAll("iframe"))f.contentWindow.postMessage({t:"draft-theme",v},"*");}
addEventListener("message",e=>{const d=e.data;if(!d||d.t!=="draft-frame"||got[d.id])return;got[d.id]=d.r;
  const f=document.querySelector(`iframe[data-id="${d.id}"]`);if(f)f.style.height=Math.max(d.h,24)+"px";
  if(Object.keys(got).length===N)done();});
function done(){const per={};
  for(const [id,r] of Object.entries(got)){const k=id.split("~")[0];const a=per[k]||(per[k]={문장:[],묻는말:[],크기:new Set(),색:[],이름:[],단추:[],넘침:[],글자:0,첫글자:null,색칠:0});
    for(const x of ["문장","묻는말","색","이름","단추","넘침"])a[x].push(...r[x]);r.크기.forEach(s=>a.크기.add(s));a.글자+=r.글자;a.색칠+=r.색칠;if(id.endsWith("~1"))a.첫글자=r.글자;}
  const res={};
  for(const [k,a] of Object.entries(per)){const bad=[];
    if(a.문장.length)bad.push("문장 "+a.문장.length);if(a.묻는말.length)bad.push("묻는 말 "+a.묻는말.length);if(a.크기.size>3)bad.push("크기 "+a.크기.size);if(a.색.length)bad.push("색 "+a.색.length);
    if(a.이름.length)bad.push("이름 "+a.이름.length);if(a.단추.length)bad.push("단추 "+a.단추.length);if(a.넘침.length)bad.push("넘침 "+a.넘침.length);
    res[k]={bad,첫글자:a.첫글자,글자:a.글자,크기:[...a.크기],색칠:a.색칠,문장:a.문장,묻는말:a.묻는말,색:a.색,이름:a.이름,단추:a.단추,넘침:a.넘침};
    const el=document.querySelector(`.ft[data-k="${k}"] .c`);
    if(el){el.textContent=(bad.length?"! "+bad.join(" · "):"✓")+"  ·  첫 화면 글 "+a.첫글자+"자";el.classList.toggle("bad",!!bad.length);
      el.title=JSON.stringify(res[k],null,1);}}
  const pg=document.querySelector(".pg");
  document.getElementById("결과").textContent=JSON.stringify({W:Math.ceil(pg.getBoundingClientRect().width),H:Math.ceil(pg.getBoundingClientRect().height),안:res});}
</script></body></html>"""


def build(folder: Path, dark: bool) -> int:
    meta = json.loads((folder / "초안.json").read_text("utf-8"))
    ic = icons()
    css = (HERE / "theme.css").read_text("utf-8")
    check = (HERE / "check.js").read_text("utf-8")
    W = int(meta.get("폭", 360))
    cols = []
    if (folder / "지금.html").exists():
        cols.append({"id": "지금", "이름": "", "file": folder / "지금.html"})
    for a in meta["안"]:
        cols.append({**a, "file": folder / f"{a['id']}.html"})
    side = len(cols) * (W + 24) <= MAX_W
    FR, cells = {}, []
    maxf = 0
    parsed = []
    for c in cols:
        if not c["file"].exists():
            print(f"없음: {c['file'].name}")
            return 1
        own, fs = frames(c["file"].read_text("utf-8"), ic)
        if not fs:
            print(f"{c['file'].name}: <section data-frame=…> 이 없다")
            return 1
        parsed.append((c, own, fs))
        maxf = max(maxf, len(fs))
    circ = "①②③④⑤⑥⑦⑧⑨⑩"
    row = 1
    for ci, (c, own, fs) in enumerate(parsed):
        col = ci + 1 if side else 1
        r0 = 1 if side else row
        rec = '<span class="rec" aria-label="추천">✦</span>' if c.get("추천") else ""
        key = c["id"]
        head = f'<span class="k">{html.escape(key)}</span>' if key != "지금" else '<span class="n">지금</span>'
        cells.append(f'<div class="ch" style="grid-column:{col};grid-row:{r0}">{head}<span class="n">{html.escape(c.get("이름", ""))}</span>{rec}</div>')
        for fi, (name, body) in enumerate(fs):
            fid = f"{key}~{fi + 1}"
            FR[fid] = doc(own, body, fid, "light", check, css)
            cells.append(f'<div class="cell" style="grid-column:{col};grid-row:{r0 + 1 + fi}"><div class="cap">{circ[fi] if fi < 10 else fi + 1} {html.escape(name)}</div>'
                         f'<iframe data-id="{fid}" width="{W}" scrolling="no"></iframe></div>')
        frow = r0 + 1 + (maxf if side else len(fs))
        ft = ""
        if key != "지금":
            ft = (f'<span class="p">+ {html.escape(c.get("이점", ""))}</span><span class="m">− {html.escape(c.get("손해", ""))}</span>')
        cells.append(f'<div class="ft" data-k="{html.escape(key)}" style="grid-column:{col};grid-row:{frow}">{ft}<span class="c"></span></div>')
        row = frow + 1
    pw = len(cols) * W + (len(cols) - 1) * 24 if side else W
    why = meta.get("까닭", "")
    page = (PAGE.replace("__THEME__", css)
            .replace("__TITLE__", html.escape(meta.get("제목", "초안")))
            .replace("__DO__", html.escape(meta.get("할 일", "")))
            .replace("__PASS__", "".join(f'<span class="chip">{html.escape(p)}</span>' for p in meta.get("합격선", [])))
            .replace("__COLS__", f"repeat({len(cols)},{W}px)" if side else f"{W}px")
            .replace("__CELLS__", "\n".join(cells))
            .replace("__WHY__", f'<div class="why"><b>✦</b> {html.escape(why)}</div>' if why else "")
            .replace("__PW__", str(max(pw, 480)))
            .replace("__SUN__", svg("sun-moon", ic))
            .replace("__FRAMES__", json.dumps(FR, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__CHECKS__", "0"))
    out = folder / "비교.html"
    out.write_text(page, "utf-8")

    chrome = _chrome()
    if not chrome:
        print(f"비교.html 만듦 · 크롬·엣지가 없어 그림·검사는 못 함")
        return 0
    res = _run(chrome, out, ["--dump-dom"], None)
    m = re.search(r'<pre id="결과" hidden="">([\s\S]*?)</pre>', res)
    if not m or not m.group(1).strip():
        print("검사 결과를 못 읽음(칸이 다 안 그려짐) — 비교.html 을 열어 확인")
        return 1
    R = json.loads(html.unescape(m.group(1)))
    w, h = R["W"] + 1, R["H"] + 1
    scale = 2 if w <= 2000 else 1  # 폰에서 확대해 읽을 수 있게
    for th, name in [("light", "비교.png")] + ([("dark", "비교-어둠.png")] if dark else []):
        _run(chrome, out, [f"--screenshot={folder / name}", f"--window-size={w},{h}", f"--force-device-scale-factor={scale}", "--hide-scrollbars"], f"?shot&theme={th}")
    shown = out.relative_to(VAULT).as_posix() if out.is_relative_to(VAULT) else str(out)
    print(f"비교 한 장: {shown} · 그림 {'나란히' if side else '세로'} {w}×{h}px ×{scale}")
    bad = 0
    for k, r in R["안"].items():
        line = "✓" if not r["bad"] else "! " + " · ".join(r["bad"])
        print(f"  {k}: {line} · 첫 화면 글 {r['첫글자']}자 · 크기 {r['크기']} · 색칠 {r['색칠']}")
        for x in ("문장", "묻는말", "색", "이름", "단추", "넘침"):
            if r[x]:
                print(f"      {x}: {r[x][:4]}")
        bad += bool(r["bad"]) and k != "지금"
    return 2 if bad else 0


def _chrome() -> str | None:
    for p in [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p):
            return p
    return shutil.which("chrome") or shutil.which("msedge")


def _run(chrome: str, page: Path, extra: list[str], query: str | None) -> str:
    prof = tempfile.mkdtemp(prefix="draft-")
    try:
        url = page.resolve().as_uri() + (query or "")
        r = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", f"--user-data-dir={prof}",
                            "--allow-file-access-from-files", "--virtual-time-budget=5000", *extra, url],
                           capture_output=True, timeout=90, creationflags=NOWIN)
        return r.stdout.decode("utf-8", "replace")
    finally:
        shutil.rmtree(prof, ignore_errors=True)


SKEL_JSON = {"제목": "", "할 일": "", "합격선": ["", ""], "폭": 360,
             "안": [], "까닭": ""}
SKEL_HTML = """<style>
/* 이 안만의 꼴 — 색·글자·간격은 var(--…) 만(theme.css) */
</style>
<section data-frame="첫 화면">
  <div class="bb-tp-sec"><div class="bb-tp-sec-head"><span class="bb-tp-sec-ic"><i data-icon="folder"></i></span><span>묶음</span><span class="bb-tp-sec-n">2</span></div>
    <div class="bb-tp-sec-body">
      <div class="bb-tp-row"><span class="bb-tp-ic"><i data-icon="file"></i></span><span class="bb-tp-text" data-d>자료 이름</span><span class="bb-tp-flair" data-d>D-3</span></div>
    </div></div>
</section>
<section data-frame="누른 뒤">
</section>
"""


def new(folder: Path, n: int) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    ids = "ABCD"[:n]
    meta = dict(SKEL_JSON, 안=[{"id": i, "이름": "", "이점": "", "손해": "", **({"추천": True} if i == "A" else {})} for i in ids])
    if not (folder / "초안.json").exists():
        (folder / "초안.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    for i in ids:
        if not (folder / f"{i}.html").exists():
            (folder / f"{i}.html").write_text(SKEL_HTML, "utf-8")
    print(f"뼈대: {folder} · 초안.json + {', '.join(i + '.html' for i in ids)}")
    return 0


def icon_find(word: str) -> int:
    ic = icons()
    names = sorted(set(ic["table"]) | set(ic["alias"]))
    hit = [n for n in names if word in n]
    print(f"{len(ic['table'])}개 중 «{word}»: " + " ".join(hit[:60]) if hit else f"«{word}» 없음")
    for n in hit:
        if n in ic["alias"]:
            print(f"  별칭 {n} → {ic['alias'][n]}")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("new", "build", "icon"):
        print(__doc__)
        sys.exit(1)
    if a[0] == "icon":
        sys.exit(icon_find(a[1] if len(a) > 1 else ""))
    f = Path(a[1])
    f = f if f.is_absolute() else (Path.cwd() / f)
    if a[0] == "new":
        sys.exit(new(f, int(a[2]) if len(a) > 2 else 3))
    sys.exit(build(f, "--dark" in a))
