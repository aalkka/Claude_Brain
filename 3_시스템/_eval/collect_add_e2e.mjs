// 수집 추가 끝까지 시험(collect-add · 11-06) — 격리 옵시디언에서 «＋ 수집 추가» → 진짜 Claude 가 대화창에서 collect_desk:add 를 돈다.
// ⚠ 진짜 모델 호출(구독 사용량) · 공개 사이트를 실제로 받는다(사이트당 1분 1회 이하는 스킬이 지킨다).
// 볼트·C:\brain-base 에 쓰지 않는다 — 임시 폴더를 현재 폴더로 · 플러그인 = C:/brain-base/build · 포트 BB_PORT(기본 9394).
//   node collect_add_e2e.mjs up          — 시험 볼트를 꾸미고 옵시디언을 띄운 채 둔다(백그라운드로 · `quit` 파일이 생기면 끈다)
//   node collect_add_e2e.mjs do add      — 수집 창 «＋ 수집 추가»를 누르고 대화창을 보인다
//   node collect_add_e2e.mjs do say "글"  — 입력 상자에 글을 넣고 보낸 뒤, 답이 끝나거나 승인 카드가 뜰 때까지 기다린다
//   node collect_add_e2e.mjs do allow    — 첫 승인 카드 «허용» · 다시 기다린다
//   node collect_add_e2e.mjs do read | desk | spawns | shot <이름>
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const cwd = path.resolve(".").replace(/\\/g, "/");
if (cwd.startsWith("C:/Claude_Brain") || cwd.startsWith("C:/brain-base")) throw new Error("임시 폴더에서 돌릴 것");
const PORT = +(process.env.BB_PORT ?? 9394);
const REAL = "C:/Claude_Brain";
const MOD = ".claude/skills/collect_desk";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const [cmd, sub, ...rest] = process.argv.slice(2);

if (cmd === "up") {
  const { launch, TV } = await import("file:///C:/brain-base/test/obs_cdp.mjs");
  const cp = (rel) => {
    const a = path.join(REAL, rel);
    if (fs.existsSync(a)) fs.cpSync(a, path.join(TV, rel), { recursive: true });
  };
  fs.rmSync(TV, { recursive: true, force: true });
  for (const r of [MOD, "3_시스템/views.json", "CLAUDE.md", "3_시스템/collect", "3_시스템/lms/courses.json", "3_시스템/lms/candidates.json", "3_시스템/lms/manifest.json", "3_시스템/_index/collect/web.log", "3_시스템/_index/collect/평가.json", "3_시스템/_index/lms/manifest.json", "3_시스템/_index/lms/runs", "3_시스템/_index/수집-대기열.md", "2_지식/일/외부뇌/알림-설정.md", "2_지식/일정"]) cp(r);
  for (const f of ["brain.py", "roles.py", "roles.json", "fileops.py", "claude_bin.py", "alarms.py", "schedule.py", "web-collect.py", "lms-auto.py", "notice-filter.py"]) cp("3_시스템/" + f);
  for (const f of fs.readdirSync(path.join(REAL, "3_시스템/_index/collect"))) if (f.endsWith(".json")) cp("3_시스템/_index/collect/" + f);
  fs.rmSync(path.join(TV, MOD, "scripts/__pycache__"), { recursive: true, force: true });
  fs.writeFileSync(path.join(TV, "3_시스템/ingest_vision.py"), "def subscription():\n    return '시험 멈춤'\n");
  // 행위는 수집 창 것(collect_desk.*)만 — 코어 actions.json 에서 · 화면·입구는 코어 views.json(수집 본체 통합 · 4단계부터 module.json 없음)
  fs.writeFileSync(path.join(TV, "3_시스템/actions.json"), JSON.stringify({ schema: 1, actions: JSON.parse(fs.readFileSync(path.join(REAL, "3_시스템/actions.json"), "utf8")).actions.filter((a) => a.id.startsWith("collect_desk.")) }));
  const PLUG = path.join(TV, ".obsidian/plugins/brain-base");
  fs.mkdirSync(PLUG, { recursive: true });
  for (const f of ["main.js", "manifest.json", "styles.css"]) fs.copyFileSync(path.join("C:/brain-base/build", f), path.join(PLUG, f));
  fs.writeFileSync(path.join(TV, ".obsidian/community-plugins.json"), '["brain-base"]');
  fs.rmSync(path.join(cwd, "quit"), { force: true });
  const { ev, close } = await launch(PORT);
  // 시험 볼트는 신뢰 안 한 폴더라 claude 가 .claude/skills 의 플러그인(collect_desk:add·fix)을 건너뛴다(`claude plugin list` 11-06 잼 · 실제 볼트는 신뢰돼 읽힘).
  // 설정 파일을 쓰지 않고 대화창 엔진을 띄울 때만 --plugin-dir 로 같은 사본을 준다 · 띄운 claude 를 모두 적는다(사용량 세기)
  const PDIR = path.join(TV, MOD).replace(/\\/g, "/");
  await ev(`const cp = require("child_process"); if (!window.__spawns) { window.__spawns = []; const o = cp.spawn;
    cp.spawn = function (exe, args, opt) { args = (args || []).map(String);
      if (/claude/i.test(String(exe)) && args.includes("--permission-prompt-tool")) args = [...args, "--plugin-dir", ${JSON.stringify(PDIR)}];
      window.__spawns.push({ exe: String(exe), args, at: Date.now() }); return o.call(this, exe, args, opt); }; } return 1`);
  await ev(`document.querySelector(".modal-container .modal-close-button")?.click(); app.commands.executeCommandById("brain-base:module-view-collect_desk-desk"); return 1`);
  fs.writeFileSync(path.join(cwd, "e2e-up.json"), JSON.stringify({ port: PORT, vault: TV, at: new Date().toISOString() }));
  console.log(`떠 있음 · 볼트 ${TV} · 포트 ${PORT}`);
  while (!fs.existsSync(path.join(cwd, "quit"))) await sleep(1000);
  await close();
  console.log("끔");
  process.exit(0);
}

// ── do: 떠 있는 옵시디언에 붙어 한 가지를 하고 끝낸다 ──
async function attach(pick) {
  const t = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(pick);
  if (!t) throw new Error("대상 없음");
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let seq = 0;
  const pend = new Map();
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pend.has(d.id)) (pend.get(d.id)(d), pend.delete(d.id));
  };
  const ev = async (expr) => {
    const id = ++seq;
    const d = await new Promise((res) => (pend.set(id, res), ws.send(JSON.stringify({ id, method: "Runtime.evaluate", params: { expression: `(async () => { ${expr} })()`, awaitPromise: true, returnByValue: true } }))));
    if (d.result?.exceptionDetails) throw new Error(d.result.exceptionDetails.exception?.description ?? d.result.exceptionDetails.text);
    return d.result?.result?.value;
  };
  const shot = async (name) => {
    const id = ++seq;
    const d = await new Promise((res) => (pend.set(id, res), ws.send(JSON.stringify({ id, method: "Page.captureScreenshot", params: { format: "png" } }))));
    if (d.result?.data) fs.writeFileSync(path.join(cwd, name), Buffer.from(d.result.data, "base64"));
  };
  return { ev, shot, close: () => ws.close() };
}
const main = await attach((x) => x.type === "page" && /index\.html/.test(x.url));
const V = `const v = app.workspace.getLeavesOfType("brain-base-chat")[0]?.view;`;
const state = () => main.ev(`${V} if (!v) return null; return { busy: v.busy, perm: [...v.listEl.querySelectorAll('.bb-perm')].map((c) => c.innerText.slice(0, 600)), ctx: v.ctx, sid: v.sessionId, mode: v.mode, entry: v.entry }`);
const transcript = (n = 6000) => main.ev(`${V} return v ? v.listEl.innerText.slice(-${n}) : "(대화창 없음)"`);
async function idle(ms = 540000) {
  const t = Date.now();
  await sleep(1500);
  for (;;) {
    const s = await state();
    if (s && (!s.busy || s.perm.length)) return { ...s, sec: Math.round((Date.now() - t) / 1000) };
    if (Date.now() - t > ms) return { ...s, sec: Math.round((Date.now() - t) / 1000), timeout: true };
    await sleep(1000);
  }
}
const report = async (s) => {
  console.log(await transcript(+(process.env.E2E_TAIL ?? 3500)));
  console.log(`\n── 상태: ${JSON.stringify({ busy: s?.busy, perm: s?.perm?.length ?? 0, ctx: s?.ctx, sid: s?.sid?.slice(0, 8), mode: s?.mode, sec: s?.sec, timeout: s?.timeout })}`);
  for (const p of s?.perm ?? []) console.log(`── 승인 카드:\n${p}`);
};
try {
  if (sub === "add") {
    const f = await attach((x) => x.type === "iframe" && x.url === "about:srcdoc");
    await f.ev(`document.querySelector('[data-add]').click(); return 1`);
    f.close();
    await sleep(1500);
    await report(await state());
  } else if (sub === "say") {
    const text = rest.join(" ");
    await main.ev(`${V} v.inputEl.value = ${JSON.stringify(text)}; await v.send(); return 1`);
    await report(await idle());
  } else if (sub === "allow") {
    await main.ev(`${V} v.listEl.querySelector('.bb-perm .mod-cta').click(); return 1`);
    await report(await idle());
  } else if (sub === "wait") await report(await idle());
  else if (sub === "read") await report(await state());
  else if (sub === "desk") {
    const f = await attach((x) => x.type === "iframe" && x.url === "about:srcdoc");
    console.log(await f.ev(`return [...document.querySelectorAll('.lr')].map((r) => (r.dataset.sel ?? '+') + ' · ' + r.innerText.replace(/\\n/g, ' ')).join('\\n')`));
    f.close();
  } else if (sub === "shot") await main.shot(rest[0] ?? "e2e.png");
  else if (sub === "spawns") console.log(await main.ev(`return (window.__spawns || []).filter((s) => /claude/i.test(s.exe)).map((s) => new Date(s.at).toTimeString().slice(0, 8) + " " + (s.args.includes("--permission-prompt-tool") ? "엔진 " + (s.args[s.args.indexOf("--model") + 1] ?? "") : s.args.includes("haiku") ? "길잡이" : "사용량")).join("\\n")`));
  else throw new Error(`모르는 명령: ${sub}`);
} finally {
  main.close();
}
process.exit(0);
