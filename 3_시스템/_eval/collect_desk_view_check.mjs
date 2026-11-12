// 수집 창(collect_desk) 화면 시험 — 격리 옵시디언 · 임시 프로필 · 포트 9377 · 진짜 설정의 읽기 사본 · 내 컴퓨터 안 시험 서버.
// 실행: 임시 폴더를 현재 폴더로 두고 `node C:/Claude_Brain/3_시스템/_eval/collect_desk_view_check.mjs`. 볼트·C:\brain-base 에 쓰지 않는다. 학교 서버에 요청이 안 나간다.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { launch, sleep, TV, OUT } from "file:///C:/brain-base/test/obs_cdp.mjs";

const cwd = path.resolve(".").replace(/\\/g, "/");
if (cwd.startsWith("C:/Claude_Brain") || cwd.startsWith("C:/brain-base")) throw new Error("임시 폴더에서 돌릴 것");
process.env.DESK_NO_OPEN = "1"; // 시험에서는 브라우저를 안 띄운다
const PORT = +(process.env.BB_PORT ?? 9377);   // 시험마다 다른 포트를 줄 수 있다(동시에 도는 시험끼리 겹치지 않게)
const REAL = "C:/Claude_Brain";
const MOD = ".claude/skills/collect_desk";
const SWF = "3_시스템/collect.local.json"; // 전체 스위치 all_off·auto_judge(수집 본체 통합 11-07) — 진짜 볼트 것은 안 옮긴다(기본 = 없음)
const cp = (rel) => {
  const a = path.join(REAL, rel);
  if (fs.existsSync(a)) fs.cpSync(a, path.join(TV, rel), { recursive: true });
};
fs.rmSync(TV, { recursive: true, force: true });
for (const r of [MOD, "3_시스템/views.json", "3_시스템/collect", "3_시스템/tutorial", "3_시스템/lms/courses.json", "3_시스템/lms/candidates.json", "3_시스템/lms/manifest.json", "3_시스템/_index/collect/web.log", "3_시스템/_index/collect/평가.json", "3_시스템/_index/lms/manifest.json", "3_시스템/_index/lms/auto.log", "3_시스템/_index/lms/runs", "3_시스템/_index/수집-대기열.md", "2_지식/일/외부뇌/알림-설정.md", "2_지식/일/외부뇌/자격-카드.md", "2_지식/일정"]) cp(r);
for (const f of ["brain.py", "roles.py", "roles.json", "fileops.py", "claude_bin.py", "alarms.py", "schedule.py", "web-collect.py", "lms-auto.py", "notice-filter.py"]) cp("3_시스템/" + f);
for (const f of fs.readdirSync(path.join(REAL, "3_시스템/_index/collect"))) if (f.endsWith(".json")) cp("3_시스템/_index/collect/" + f);
fs.writeFileSync(path.join(TV, "3_시스템/ingest_vision.py"), "def subscription():\n    return '시험 멈춤'\n"); // 판정은 구독 관문에서 멈춘다 — claude 를 안 부른다
// 행위는 수집 창 것(collect_desk.*)만 — 코어 actions.json 에서 · 화면·입구는 코어 views.json(수집 본체 통합 · 4단계부터 module.json 없음) · 다른 코어 행위는 안 둔다
const deskActs = JSON.parse(fs.readFileSync(path.join(REAL, "3_시스템/actions.json"), "utf8")).actions.filter((a) => a.id.startsWith("collect_desk."));
fs.writeFileSync(path.join(TV, "3_시스템/actions.json"), JSON.stringify({ schema: 1, actions: deskActs }));
// 실제 상태에 기대지 않게 씨앗(11-06 실제는 후보 0 · 판정 대기 0 이라 «손이 필요한 곳»·후보 단추 시험이 비었다) — 후보 둘 · 과학 공지에 판정 대기 한 건
fs.writeFileSync(path.join(TV, "3_시스템/lms/candidates.json"), JSON.stringify({ candidates: [
  { id: "zz-cand-1", name: "시험 후보 하나", host: "one.example", url: "http://one.example/", measured: "시험", note: "시험" },
  { id: "zz-cand-2", name: "시험 후보 둘", host: "two.example", url: "http://two.example/", measured: "시험", note: "시험" }] }));
{
  const sp = path.join(TV, "3_시스템/_index/collect/ku-science-notice.json");
  const st = fs.existsSync(sp) ? JSON.parse(fs.readFileSync(sp, "utf8")) : { items: {} };
  st.items.zz9001 = { title: "시험 판정 대기 글", date: "2026-11-01", run: "20261101-0000", stage: true };
  fs.writeFileSync(sp, JSON.stringify(st));
}
const runsDir = path.join(TV, "3_시스템/_index/lms/runs");
const extNew = JSON.parse(fs.readFileSync(path.join(TV, "3_시스템/lms/manifest.json"), "utf8")).version;
fs.writeFileSync(path.join(runsDir, "lms-run-시험판.json"), JSON.stringify({ kind: "status", login: "ok", at: Date.now(), version: extNew })); // 새 판 확장이 돈 뒤의 모습
const PLUG = path.join(TV, ".obsidian/plugins/brain-base");
fs.mkdirSync(PLUG, { recursive: true });
for (const f of ["main.js", "manifest.json", "styles.css"]) fs.copyFileSync(path.join(REAL, ".obsidian/plugins/brain-base", f), path.join(PLUG, f));
fs.writeFileSync(path.join(TV, ".obsidian/community-plugins.json"), '["brain-base"]');

// 시험 출처 — 내 컴퓨터 안 서버
const hits = [];
const srv = http.createServer((q, s) => {
  hits.push(q.url);
  s.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  if (q.url.startsWith("/view")) s.end(`<h1>글 ${q.url.split("=").pop()} 제목</h1><div id=b>본문</div>`);
  else s.end("<table><tr><td>id=zz201</td><b>새 글</b><i>2026-11-01</i></tr></table>");
});
await new Promise((r) => srv.listen(0, "127.0.0.1", r));
const WEB = srv.address().port;
const R = JSON.parse(fs.readFileSync(path.join(TV, "3_시스템/roles.json"), "utf8")).roles;
const LOCAL = "t-local";
const LP = `3_시스템/collect/${LOCAL}.json`;
fs.writeFileSync(path.join(TV, LP), JSON.stringify({
  id: LOCAL, name: "시험 출처", contract: "시험", family: "regex", page: `http://127.0.0.1:${WEB}/`, folder: "@school_notice/시험", filter: { title_skip: "거를말" },
  list: { page_url: `http://127.0.0.1:${WEB}/list?p={page}`, pages: 1, row: "<tr>(.*?)</tr>", fields: { id: "id=(zz\\d+)", title: "<b>(.*?)</b>", date: "<i>(.*?)</i>" } },
  view: { url: `http://127.0.0.1:${WEB}/view?id={id}`, title: "<h1>(.*?)</h1>", body: "<div id=b>(.*?)</div>" },
}));
const ARCREL = `${R.school_notice}/시험/2026-10-01 보관 글.md`;
fs.mkdirSync(path.dirname(path.join(TV, "3_시스템/_index/collect/archive", ARCREL)), { recursive: true });
fs.writeFileSync(path.join(TV, "3_시스템/_index/collect/archive", ARCREL), "# 보관 글\n");
fs.writeFileSync(path.join(TV, `3_시스템/_index/collect/${LOCAL}.json`), JSON.stringify({ last_run: 0, page1_rows: 1, items: {
  zz301: { title: "장부 글", date: "2026-11-01", run: "20261101-0000", verdict: "비해당", why: "제목 관심 밖" },
  zz303: { title: "보관 글", date: "2026-10-01", run: "20261001-0000", verdict: "비해당", why: "조건", archived: ARCREL },
} }));
const J = (rel) => JSON.parse(fs.readFileSync(path.join(TV, rel), "utf8"));
const ST = () => J(`3_시스템/_index/collect/${LOCAL}.json`).items;
const LEDGER = () => fs.readFileSync(path.join(TV, "3_시스템/ledger/actions.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
const SCI = "ku-science-notice";
const RC = `3_시스템/collect/${SCI}.json`;

const IR = () => JSON.parse(execFileSync("py", ["-3", path.join(TV, MOD, "scripts/collect_desk.py"), "view"], { encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } }).trim());
const data = IR();
const sci = data.sources.find((s) => s.id === SCI);
const open1 = sci.items.find((x) => x.where === "vault" && x.path !== "");
const vaultNote = sci.items.find((x) => x.where === "vault")?.title;

const { ev, shot, close, send } = await launch(PORT);
let fails = 0;
const ok = (name, cond, extra = "") => (console.log(`${cond ? "통과" : "실패"} ${name}${!cond && extra ? " — " + extra : ""}`), cond || fails++);
let frameWs = null;
let seq = 0;
const waiting = new Map();
async function frameCtx() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const t = list.find((x) => x.type === "iframe" && x.url === "about:srcdoc");
  if (!t) return null;
  frameWs?.close();
  frameWs = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((r) => (frameWs.onopen = r));
  frameWs.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && waiting.has(d.id)) (waiting.get(d.id)(d), waiting.delete(d.id));
  };
  return t.id;
}
const inFrame = async (expr) => {
  const id = ++seq;
  const d = await new Promise((res) => {
    waiting.set(id, res);
    frameWs.send(JSON.stringify({ id, method: "Runtime.evaluate", params: { expression: `(() => { ${expr} })()`, returnByValue: true } }));
  });
  if (d.error) throw new Error(JSON.stringify(d.error));
  if (d.result.exceptionDetails) throw new Error(d.result.exceptionDetails.exception?.description ?? d.result.exceptionDetails.text);
  return d.result.result.value;
};
const until = async (fn, ms = 15000) => {
  const t = Date.now();
  while (Date.now() - t < ms) {
    if (await Promise.resolve().then(fn).catch(() => false)) return true;
    await sleep(200);
  }
  return false;
};
const q = (s) => JSON.stringify(s);
const clickF = (src, f) => inFrame(`document.querySelector('[data-src="${src}"][data-f="${f}"]').click(); return 1`);
// 전체·자동 판정·크롬 열기·PC 깨우기는 톱니 작은 창 안(11-12 안 3 가) — 열려 있지 않으면 연다
const openPop = () => inFrame(`if(!document.querySelector('.pop'))document.querySelector('[data-pop]').click(); return 1`);
const select = (id) => inFrame(`document.querySelector('[data-sel="${id}"]').click(); return 1`);
const click = (sel) => inFrame(`document.querySelector(${q(sel)}).click(); return 1`);
const has = (sel) => inFrame(`return !!document.querySelector(${q(sel)})`);
const enter = (sel, v) => inFrame(`const t=document.querySelector('${sel}'); t.value=${q(v)}; t.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); t.dispatchEvent(new Event('change',{bubbles:true})); return 1`);
const text = () => inFrame(`return document.body.innerText`);
const T = `app.plugins.plugins['brain-base'].tutorial`;
const CMD = "brain-base:module-view-collect_desk-desk";
try {
  await ev(`document.querySelector(".modal-container .modal-close-button")?.click(); return 1`); // 시험 볼트 첫 열림의 신뢰 창
  ok("명령이 생김", await until(() => ev(`return !!app.commands.commands["${CMD}"]`)));

  // ── 튜토리얼 장 ──
  const cid = "8-수집"; // 코어 8장(4단계에 모듈 장 collect_desk:1-수집 을 옮김 · 머리 «화면:»·«옛 id:»)
  ok("튜토리얼 장 = 코어 8장 · 화면 collect_desk", await until(() => ev(`const l = await ${T}.load(); return l.some((c) => c.id === ${q(cid)} && c.no === 8 && c.view === "collect_desk")`)));
  await ev(`await ${T}.start(${q(cid)}); return 1`);
  let steps = 0, stuck = "";
  for (let n = 0; n < 12; n++) {
    await until(() => ev(`return !${T}.moving`));
    const st = await ev(`const t = ${T}; return { name: t.step?.name ?? null, i: t.i, wait: t.step?.wait ?? '', point: t.step?.point ?? '', ended: t.ended }`);
    if (st.ended) break;
    steps++;
    if (st.wait === "보임 모듈화면") {
      await until(() => ev(`const t = ${T}; t.draw(); return !!t.find(${q(st.point)})`));
      await ev(`${T}.find(${q(st.point)}).click(); return 1`);
    } else await ev(`document.querySelector('.bb-tt-card button.mod-cta')?.click(); return 1`);
    if (!(await until(async () => { const now = await ev(`const t = ${T}; return { i: t.i, ended: t.ended }`); return now.ended || now.i !== st.i; }))) { stuck = st.name; break; }
  }
  ok("튜토리얼 장 끝까지(7단계)", steps === 7 && !stuck, `단계 ${steps} · 멈춤 ${stuck}`);
  await ev(`[...document.querySelectorAll('.bb-tt-card button')].find((b) => b.textContent === '닫기')?.click(); return 1`);
  await sleep(600);
  ok("튜토리얼 끝 = 화면이 닫힘", await until(() => ev(`return app.workspace.getLeavesOfType('brain-module-view').length === 0`)));

  // ── 읽기 ── (곁창을 접고 연다 — 곁창 바로 옆이면 위쪽 꼴(.ch)이라 왼쪽 나무(.lr)를 재는 줄이 선다 · 11-06 collect-add)
  await ev(`app.workspace.leftSplit.collapse(); return 1`);
  await ev(`app.commands.executeCommandById("${CMD}"); return 1`);
  ok("화면 대상이 뜸", await until(async () => !!(await frameCtx())));
  ok("자료가 그려짐", await until(() => inFrame(`return document.querySelectorAll('.lr').length > 0`)));
  ok("왼쪽 줄 수 = 출처 + 후보", (await inFrame(`return document.querySelectorAll('.lr:not(.add)').length`)) === data.sources.length + data.candidates.length, String(data.sources.length));
  const mine = await inFrame(`return firstMine().id`); // 화면의 차례 그대로(실패·로그인 끊김 → 경고 → 첫 출처) — 진짜 상태 사본이라 어느 출처가 먼저인지는 그날 상태에 따른다
  ok("처음 고를 출처 = 진짜 출처", data.sources.some((s) => s.id === mine), mine);
  ok("처음 고른 출처 = 손이 필요한 곳", (await inFrame(`return document.querySelector('.lr.sel').dataset.sel`)) === mine, mine);
  await ev(`document.querySelectorAll(".modal-container").forEach((m) => (m.style.display = "none")); return 1`); // 그림을 가리는 신뢰 창 — 눌러 닫지 않고 가리기만
  await sleep(500);
  await shot("collect-wide.png");

  await select("mylms");
  const m = data.sources.find((s) => s.id === "mylms");
  const tm = await text();
  ok("mylms 숫자", [m.tot.posts, m.tot.files, m.tot.board].every((n) => tm.includes(String(n))), JSON.stringify(m.tot));
  ok("mylms 과목 줄", (await inFrame(`return document.querySelectorAll('.crow').length`)) === m.courses.length, String(m.courses.length));
  ok("mylms 알림", tm.includes(`${m.alarm.days.join("·")}일 전 ${m.alarm.at.join(" ")}`));
  ok("확장 칸 = 새 판 · 옛 판 표시 없음", tm.includes(extNew) && !tm.includes("옛 판"));
  ok("지금 받기 단추 있음", await has('[data-fetch="mylms"]'));
  await openPop();
  ok("톱니 작은 창 = PC 깨우기·크롬 열기·자동 판정·전체", await until(async () => (await inFrame(`return [...document.querySelectorAll('.pop span')].map(x=>x.textContent).join('·')`)) === "PC 깨우기·크롬 열기·자동 판정·전체"));
  fs.writeFileSync(path.join(runsDir, "lms-run-시험판.json"), JSON.stringify({ kind: "status", login: "ok", at: Date.now(), version: "0.0.1" }));
  ok("옛 판 = 표시 · 지금 받기 단추 없음", await until(async () => (await text()).includes("옛 판") && !(await has('[data-fetch="mylms"]'))));
  fs.writeFileSync(path.join(runsDir, "lms-run-시험판.json"), JSON.stringify({ kind: "status", login: "ok", at: Date.now(), version: extNew }));
  await until(() => has('[data-fetch="mylms"]'));
  await shot("collect-mylms.png");
  await click('[data-open="mylms"]');
  ok("로그인·사이트 단추 = 행위로 연다", await until(() => LEDGER().some((e) => e.action === "collect_desk.open" && e.args.source === "mylms" && e.code === 0)));

  await select(SCI);
  await click('[data-seg="pend"]');
  ok("판정 대기 칸 줄 수", (await inFrame(`return document.querySelectorAll('.it').length`)) === sci.cnt.pend, String(sci.cnt.pend));
  await click('[data-seg="vault"]');
  ok("볼트 칸 줄 수", (await inFrame(`return document.querySelectorAll('.it').length`)) === sci.cnt.vault, String(sci.cnt.vault));
  const noteFile = "2_지식/시험 글.md";
  fs.mkdirSync(path.join(TV, "2_지식"), { recursive: true });
  fs.writeFileSync(path.join(TV, noteFile), "# 시험 글\n");
  await sleep(500);
  await inFrame(`document.querySelector('.it').classList.add('go'); document.querySelector('.it').dataset.note = ${q(noteFile)}; document.querySelector('.it .n').click(); return 1`);
  ok("글을 누르면 옆 칸에 열림", await until(() => ev(`let ok=false; app.workspace.iterateAllLeaves(l=>{ if(l.view?.file?.path===${q(noteFile)}) ok=true }); return ok`)));

  const sch = data.sources.find((s) => s.alarm && s.alarm.on && s.id !== "mylms");
  await select(sch.id);
  await sleep(1500); // 앞 글이 다 열리기 전에 또 누르면 옵시디언이 그 열기를 삼킨다(화면 문 쪽 일)
  await click(".link[data-note]");
  ok("알림 칸을 누르면 설정 노트", await until(() => ev(`let ok=false; app.workspace.iterateAllLeaves(l=>{ if(l.view?.file?.path==="2_지식/일/외부뇌/알림-설정.md") ok=true }); return ok`)));
  const AL = path.join(TV, "2_지식/일/외부뇌/알림-설정.md");
  fs.writeFileSync(AL, fs.readFileSync(AL, "utf8").replace('"며칠_전": [3, 1]', '"며칠_전": [7, 2]'));
  ok("설정을 고치면 화면이 따라옴", await until(async () => (await text()).includes("7·2일 전")));

  // ── 고치기 ──
  await select(SCI);
  await clickF(SCI, "enabled");
  ok("출처 끄기 = enabled false", await until(() => J(RC).enabled === false));
  ok("화면이 꺼짐으로", await until(() => inFrame(`return [...document.querySelectorAll('[data-sel="${SCI}"]')].some((e) => e.classList.contains('off'))`)));
  ok("끈 출처 = 판정·받기·살리기 단추 없음", await until(async () => !(await has("[data-judge]")) && !(await has("[data-fetch]")) && !(await has('[data-op="rescue"]'))));
  await until(() => inFrame(`return document.querySelector('[data-src="${SCI}"][data-f="enabled"]').dataset.v === 'true'`));
  await clickF(SCI, "enabled");
  ok("다시 켜기 = 칸이 사라짐", await until(() => !("enabled" in J(RC))));
  await until(() => inFrame(`return document.querySelector('[data-src="${SCI}"][data-f="enabled"]').dataset.v === 'false'`));

  await enter(`[data-chip="${SCI}|skip+"]`, "시험말(2)");
  ok("뺄 말 더함 = 글자 그대로 이스케이프", await until(() => J(RC).filter.title_skip.endsWith("|시험말\\(2\\)")), J(RC).filter.title_skip);
  ok("이스케이프된 낱말은 잠금 칩", await until(() => inFrame(`return [...document.querySelectorAll('.chip.lock')].some(c=>c.textContent.includes('시험말'))`)));
  await enter(`[data-chip="${SCI}|skip+"]`, "지울말");
  await until(() => J(RC).filter.title_skip.includes("지울말"));
  await until(() => has('[data-f="skip-"][data-v="지울말"]'));
  await click('[data-f="skip-"][data-v="지울말"]');
  ok("뺄 말 뺌", await until(() => !J(RC).filter.title_skip.includes("지울말")));

  await click(`[data-edit="${SCI}"]`);   // 받기 칸 연필(11-12) — 주기 고르기는 바꾸기 칸 안
  await until(() => has(`[data-hours="${SCI}"]`));
  await inFrame(`const t=document.querySelector('[data-hours="${SCI}"]'); t.value='12'; t.dispatchEvent(new Event('change',{bubbles:true})); return 1`);
  ok("주기", await until(() => J(RC).recheck_hours === 12));
  await until(() => inFrame(`return document.querySelector('[data-hours="${SCI}"]').value === '12'`));
  ok("쪽·첨부 칸 없음(Claude 몫 · 11-12)", !(await has(`[data-src="${SCI}"][data-f="pages"]`)) && !(await has(`[data-src="${SCI}"][data-f="download"]`)));
  await inFrame(`const t=document.querySelector('[data-purpose="${SCI}"]'); t.value='시험 목적'; t.dispatchEvent(new Event('change',{bubbles:true})); return 1`);
  ok("목적", await until(() => J(RC).purpose === "시험 목적"));
  // 전체 «자동 판정»(collect.local.json auto_judge · 기본 끔) — 켜야 출처별 칸이 보인다. 켤 때 묻는 창 · 취소 = 안 씀 · 없으면 끔
  ok("전체 자동 판정 = 기본 끔 · 출처별 칸은 안 보임", !(fs.existsSync(path.join(TV, SWF)) && J(SWF).auto_judge) && !(await has(`[data-src="${SCI}"][data-f="auto"]`)));
  await openPop();
  await clickF("*", "auto_judge");
  ok("전체 자동 판정 = 묻는 창이 먼저", await until(() => inFrame(`return document.querySelector('.dlg p')?.textContent === '구독 사용량을 씁니다. 자동 판정을 켜시겠습니까?'`)));
  await click(".dlg [data-n]");
  await sleep(600);
  ok("취소 = 안 씀", !(fs.existsSync(path.join(TV, SWF)) && J(SWF).auto_judge));
  await clickF("*", "auto_judge");
  await until(() => has(".dlg [data-y]"));
  await click(".dlg [data-y]");
  ok("전체 자동 판정 켜기 = collect.local.json auto_judge", await until(() => J(SWF).auto_judge === true));
  if (!(await until(() => has(`[data-src="${SCI}"][data-f="auto"]`)))) console.log("자동 판정 칸 없음:", await inFrame(`return document.querySelector('.lr.sel')?.dataset.sel + ' | ' + document.querySelector('.b-r')?.innerText.slice(0, 300)`));
  await clickF(SCI, "auto");
  ok("출처별 = 켜져 있던 것을 끔 = filter.auto false(묻지 않음)", await until(() => J(RC).filter.auto === false));
  await until(() => has(`[data-src="${SCI}"][data-f="auto"][data-v="true"]`));
  await clickF(SCI, "auto");
  ok("출처별 다시 켤 때 = 묻는 창이 먼저", await until(() => inFrame(`return document.querySelector('.dlg p')?.textContent === '구독 사용량을 씁니다. 자동 판정을 켜시겠습니까?'`)));
  await click(".dlg [data-n]");
  await sleep(600);
  ok("취소 = false 그대로", J(RC).filter.auto === false);
  const before = J(RC);
  ok("주소·정규식·계약 그대로", before.page && before.contract && before.list.row && before.view);

  // ── 지금 받기 · 판정 · 글 줄 ──
  await select(LOCAL);
  await until(() => has(`[data-fetch="${LOCAL}"]`));
  hits.length = 0;
  await click(`[data-fetch="${LOCAL}"]`);
  ok("지금 받기 = 그 자리에서 받음(시험 서버만)", await until(() => hits.includes("/view?id=zz201") && ST().zz201?.stage), JSON.stringify(hits));
  ok("받은 글 = 판정 대기 · 판정 단추", await until(() => inFrame(`return document.querySelector('[data-judge="${LOCAL}"]')?.textContent === '판정 1'`)));
  ok("받기 표시가 치워짐", await until(() => !fs.existsSync(path.join(TV, `3_시스템/_index/collect/desk-busy-${LOCAL}.txt`))));
  await click(`[data-judge="${LOCAL}"]`);
  ok("판정 = 묻는 창이 먼저", await until(() => inFrame(`return document.querySelector('.dlg p')?.textContent === '구독 사용량을 씁니다. 판정하시겠습니까?'`)));
  await click(".dlg [data-n]");
  await sleep(500);
  ok("판정 취소 = 안 돎", !LEDGER().some((e) => e.action === "collect_desk.judge"));
  await click(`[data-judge="${LOCAL}"]`);
  await until(() => has(".dlg [data-y]"));
  await click(".dlg [data-y]");
  ok("판정 = 그 출처만 부름 · 구독 관문에서 멈춤", await until(() => LEDGER().some((e) => e.action === "collect_desk.judge" && e.args.source === LOCAL && e.code === 2)));
  await until(() => has('[data-seg="pend"]'));
  await click('[data-seg="pend"]');
  await until(() => has('[data-aid="zz201"][data-op="reject"]'));
  ok("대기 칸 글을 읽을 수 있다", await inFrame(`return (document.querySelector('.it.go')?.dataset.note ?? '').endsWith('stage/${LOCAL}/zz201.md')`));
  await click('[data-aid="zz201"][data-op="reject"]');
  // 거절 창(11-09) — 제목 낱말 단추(흔한 말 «안내» 뺌) · 고르면 가로선 · 메모 · 거절 = 고른 낱말·메모가 근거·표시로
  ok("거절 = 창 · 제목 낱말 단추(글 제목 «글 zz201 제목» · 한 글자 «글» 뺌)", await until(() => inFrame(`return [...document.querySelectorAll('.dlg .wd')].map((b) => b.textContent).join('|') === 'zz201|제목'`)));
  await click('.dlg .wd[data-w="제목"]');
  ok("낱말 고름 = 가로선", await inFrame(`return getComputedStyle(document.querySelector('.dlg .wd[data-w="제목"]')).textDecorationLine.includes('line-through')`));
  await inFrame(`document.querySelector('.dlg .memo').value = '시험 메모'; return 1`);
  await click(".dlg [data-y]");
  ok("빼기 = 장부로 · 대기 칸 파일 지움 · 근거 = 낱말·메모", await until(() => ST().zz201.verdict === "비해당" && ST().zz201.why === "사용자: «제목» · 시험 메모" && !ST().zz201.stage && !fs.existsSync(path.join(TV, `3_시스템/_index/collect/stage/${LOCAL}/zz201.md`))), JSON.stringify(ST().zz201));
  const mk = J("3_시스템/_index/collect/평가.json")[`${LOCAL}:zz201`] || {};
  ok("거절 표시 = 단추 · 낱말 · 메모(되먹임이 대조 없이 씀)", mk.평가 === "헛것" && mk.길 === "단추" && JSON.stringify(mk.낱말) === '["제목"]' && mk.메모 === "시험 메모", JSON.stringify(mk));
  await until(() => has('[data-seg="ledger"]'));
  await click('[data-seg="ledger"]');
  await until(() => has('[data-aid="zz301"][data-op="rescue"]'));
  await inFrame(`const s = document.createElement('style'); s.id = 'shot'; s.textContent = '.it .act{display:inline-block!important}'; document.head.append(s); document.querySelector('.it').scrollIntoView({ block: 'center' }); return 1`);
  await shot("collect-ledger.png");
  await inFrame(`document.getElementById('shot').remove(); return 1`);
  hits.length = 0;
  await click('[data-aid="zz301"][data-op="rescue"]');
  ok("장부 글 살리기 = 받아서 볼트로", await until(() => ST().zz301.path && hits.includes("/view?id=zz301") && fs.existsSync(path.join(TV, ST().zz301.path))), JSON.stringify([hits, ST().zz301]));
  ok("살리기 = 쓸모 표시 · 일어난 일에 제목", await until(async () => J("3_시스템/_index/collect/평가.json")[`${LOCAL}:zz301`]?.평가 === "쓸모" && (await text()).includes("살림 · 글 zz301 제목")));
  await until(() => inFrame(`return document.querySelector('.stats .sel b')?.textContent === '1'`));
  await click('[data-seg="arch"]');
  await until(() => has('[data-aid="zz303"][data-op="restore"]'));
  await click('[data-aid="zz303"][data-op="restore"]');
  ok("되돌리기 = 보관 칸 → 볼트", await until(() => ST().zz303.path && fs.existsSync(path.join(TV, ARCREL))));
  await until(() => has('[data-seg="vault"]'));
  await click('[data-seg="vault"]');
  await until(() => has('[data-aid="zz303"][data-op="useless"]'));
  await click('[data-aid="zz303"][data-op="useless"]');
  ok("헛것 = 표시만 · 글 그대로", await until(() => J("3_시스템/_index/collect/평가.json")[`${LOCAL}:zz303`]?.평가 === "헛것" && fs.existsSync(path.join(TV, ARCREL))));
  ok("헛것 뒤엔 쓸모 단추", await until(() => has('[data-aid="zz303"][data-op="useful"]')));
  await click(`[data-open="${LOCAL}"]`);
  ok("주소를 누르면 행위로 연다", await until(() => LEDGER().some((e) => e.action === "collect_desk.open" && e.args.source === LOCAL && e.code === 0)));

  // ── mylms ──
  await select("mylms");
  await until(() => has('[data-f="course"]'));
  const course = await inFrame(`return document.querySelector('[data-f="course"][data-v$="=off"]').dataset.v.split('=')[0]`);
  await click(`[data-f="course"][data-v="${course}=off"]`);
  ok("과목 빼기 = _제외 로", await until(() => !J("3_시스템/lms/courses.json")[course] && J("3_시스템/lms/courses.json")._제외[course]));
  ok("과목 빼기 = known 에서 빠짐", await until(() => !J("3_시스템/lms/known.json").courses.includes(Number(course))));
  await until(() => has(`[data-f="course"][data-v="${course}=on"]`));
  await click(`[data-f="course"][data-v="${course}=on"]`);
  ok("과목 넣기 = 되돌아옴", await until(() => J("3_시스템/lms/courses.json")[course] && J("3_시스템/lms/known.json").courses.includes(Number(course))));
  await until(() => has('[data-fetch="mylms"]'));
  await click('[data-fetch="mylms"]');
  ok("mylms 지금 받기 = desk + known fetchNow", await until(() => J("3_시스템/lms/desk.json").fetch_now && J("3_시스템/lms/known.json").fetchNow === J("3_시스템/lms/desk.json").fetch_now));
  ok("mylms 받기 대기 표시", await until(async () => (await text()).includes("받기 대기")));
  await until(() => inFrame(`return document.querySelector('[data-src="mylms"][data-f="enabled"]').dataset.v === 'false'`));
  await clickF("mylms", "enabled");
  ok("mylms 끄기 = desk + known paused", await until(() => J("3_시스템/lms/desk.json").enabled === false && J("3_시스템/lms/known.json").paused === true));
  await openPop();
  ok("mylms 끔 = 크롬 열기 스위치 잠김", await until(() => inFrame(`return document.querySelector('.pop [data-f="wake"]').disabled`)));
  await inFrame(`document.querySelector('[data-pop]').click(); return 1`);
  await until(() => inFrame(`return document.querySelector('[data-src="mylms"][data-f="enabled"]').dataset.v === 'true'`));
  await clickF("mylms", "enabled");
  ok("mylms 켜기 = known paused 풀림", await until(() => J("3_시스템/lms/known.json").paused === false));

  // ── 후보 ──
  const c0 = data.candidates[0], c1 = data.candidates[1];
  await select(`cand:${c0.id}`);
  await until(() => has(`[data-cand="${c0.id}"][data-a="계약"]`));
  await shot("collect-cand.png");
  await click(`[data-cand="${c0.id}"][data-a="계약"]`);
  ok("계약 = 묻는 창이 먼저", await until(() => inFrame(`return document.querySelector('.dlg p')?.textContent === ${q(c0.name + " 수집을 계약하시겠습니까?")}`)));
  ok("묻는 동안 안 씀", !J("3_시스템/lms/candidates.json").candidates[0].answer);
  await click(".dlg [data-y]");
  ok("계약 = 답 저장 · 대기열 한 줄", await until(() => J("3_시스템/lms/candidates.json").candidates[0].answer === "계약" && fs.readFileSync(path.join(TV, "3_시스템/_index/수집-대기열.md"), "utf8").includes(`\`${c0.id}\` (Claude) 수집 계약 승인`)));
  ok("계약해도 조리법이 저절로 안 생김", !fs.existsSync(path.join(TV, `3_시스템/collect/${c0.id}.json`)));
  ok("계약 대기 표시 · mylms 실패로 안 뜸", await until(async () => (await inFrame(`return document.querySelector('[data-sel="cand:${c0.id}"]').innerText`)).includes("계약 대기") && !(await inFrame(`return document.querySelector('[data-sel="mylms"]').innerText`)).includes("실패")));
  await select(`cand:${c1.id}`);
  await until(() => has(`[data-cand="${c1.id}"][data-a="안 함"]`));
  await click(`[data-cand="${c1.id}"][data-a="안 함"]`);
  ok("안 함 = 줄이 사라짐 · 대기열 안 씀", await until(async () => !(await has(`[data-sel="cand:${c1.id}"]`))) && !fs.readFileSync(path.join(TV, "3_시스템/_index/수집-대기열.md"), "utf8").includes(c1.id));

  // ── 전체 ──
  await openPop();
  await clickF("*", "all_off");
  ok("전체 끄기 = 묻는 창", await until(() => inFrame(`return document.querySelector('.dlg p')?.textContent === '모든 수집을 끄시겠습니까?'`)));
  await click(".dlg [data-y]");
  ok("전체 끄기 = collect.local.json all_off + known paused", await until(() => J(SWF).all_off === true && J("3_시스템/lms/known.json").paused === true));
  ok("전체 끄기 = 모든 출처 줄 꺼짐", await until(() => inFrame(`return [...document.querySelectorAll('.lr:not([data-sel^="cand:"])')].every(r => r.innerText.includes('꺼짐'))`)));
  await until(() => inFrame(`return document.querySelector('[data-f="all_off"]').dataset.v === 'false'`));
  await clickF("*", "all_off");
  ok("전체 켜기", await until(() => J(SWF).all_off === false));
  ok("전체 켜기 = 화면도 켜짐으로", await until(() => inFrame(`return ![...document.querySelectorAll('.lr')].some(r => r.innerText.includes('꺼짐'))`)));
  ok("전체 스위치는 desk.json 에 안 씀", !fs.existsSync(path.join(TV, "3_시스템/lms/desk.json")) || !["all_off", "auto_judge"].some((k) => k in J("3_시스템/lms/desk.json")));

  const led = LEDGER().filter((e) => e.action === "collect_desk.set");
  ok("장부에 남음", led.length >= 12 && led.every((e) => e.code === 0), `${led.length}줄`);
  await select(SCI);
  ok("내 동작이 일어난 일에", await until(() => has(".ev .me")));
  const labels = await inFrame(`return [...document.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label'))`);
  ok("이름표 8자·기호", labels.every((l) => l.length <= 8 && !/[—(]/.test(l)), [...new Set(labels)].join(","));
  ok("가로 넘침 없음", await inFrame(`return document.documentElement.scrollWidth <= innerWidth`));
  await send("Emulation.setDeviceMetricsOverride", { width: 720, height: 900, deviceScaleFactor: 1, mobile: false });
  await sleep(600);
  await shot("collect-narrow.png");
  await send("Emulation.setDeviceMetricsOverride", { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });
  await ev(`app.changeTheme?.("obsidian"); return 1`);
  await sleep(800);
  await shot("collect-dark.png");
  console.log("쓴 그림:", OUT);
} catch (e) {
  fails++;
  console.log("실패 예외:", e.stack || e.message);
} finally {
  try { frameWs?.close(); } catch {}
  await close();
  srv.close();
}
console.log(fails ? `실패 ${fails}` : "전부 통과");
process.exit(fails ? 1 : 0);
