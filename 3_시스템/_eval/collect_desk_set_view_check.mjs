// 수집 창 받기 칸·톱니 작은 창(11-12 · 안 3 가 · 사용자 고름) — 진짜 화면 파일 + 진짜 자료(collect_desk.py view · 읽기만) + 가짜 바탕(행위를 받아 자료를 고쳐 다시 보냄).
// 머리 없는 크롬(창 0 · 포트 BB_PORT 기본 9311 · 임시 프로필) · 볼트·예약 안 건드림(행위는 화면 밖으로 안 나감).
//   node 3_시스템/_eval/collect_desk_set_view_check.mjs
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const VAULT = "C:/Claude_Brain";
const VIEW = `${VAULT}/.claude/skills/collect_desk/view/index.html`;
const PORT = +(process.env.BB_PORT ?? 9311);
const exe = execFileSync("reg", ["query", "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe", "/ve"], { encoding: "utf8" }).match(/REG_SZ\s+(.+)/)[1].trim();
const data = execFileSync("py", ["-3", `${VAULT}/.claude/skills/collect_desk/scripts/collect_desk.py`, "view"], { encoding: "utf8", cwd: VAULT, windowsHide: true }).trim().split("\n").pop();
const D0 = JSON.parse(data);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "collect-setview-"));
const HARNESS = `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;height:100%}iframe{border:0;width:1100px;height:760px}</style>
<iframe id="f" src="file:///${VIEW}"></iframe><script>
window.D=${data};window.ACTS=[];
const send=()=>f.contentWindow.postMessage({t:'data',data:JSON.parse(JSON.stringify(D))},'*');
const apply=(s,k,v)=>{if(k==='at'){s.at=v?v.split(','):[];if(s.family!=='lms')s.mode=s.at.length?'at':'every'}if(k==='hours'){s.hours=+v;s.at=[];s.mode='every'}if(k==='wake')s.wakeOn=v==='true'};
addEventListener('message',e=>{const m=e.data||{};if(m.t==='ready')send();if(m.t!=='act')return;ACTS.push(m);const a=m.args||{};
  if(m.id==='collect_desk.set'){if(a.source==='*'){if(a.field==='wake_pc')D.wakePc=a.value==='true';if(a.field==='auto_judge')D.autoJudge=a.value==='true';if(a.field==='all_off')D.allOff=a.value==='true'}
    else apply(D.sources.find(x=>x.id===a.source),a.field,a.value);setTimeout(send,20)}});
</script>`;
const h = path.join(tmp, "h.html");
fs.writeFileSync(h, HARNESS);
const chrome = spawn(exe, ["--headless=new", `--user-data-dir=${tmp}/prof`, `--remote-debugging-port=${PORT}`, "--allow-file-access-from-files", "--no-first-run", "file:///" + h.split(path.sep).join("/")], { stdio: "ignore", windowsHide: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, seq = 0;
const pend = new Map();
for (let i = 0; i < 40 && !ws; i++) {
  try {
    const p = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === "page" && t.url.startsWith("file:"));
    if (p) { ws = new WebSocket(p.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r)); }
  } catch {}
  if (!ws) await sleep(250);
}
ws.onmessage = (e) => { const m = JSON.parse(e.data); if (pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((r) => { const id = ++seq; pend.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
const IN = `const d=f.contentDocument,q=s=>d.querySelector(s),w=ms=>new Promise(r=>setTimeout(r,ms));
const click=async s=>{const e=q(s);if(!e)throw new Error('없음 '+s);e.click();await w(80)};
const type=async(s,v)=>{const e=q(s);if(!e)throw new Error('없음 '+s);e.focus();e.value=v;e.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));await w(80)};
const last=()=>{const a=ACTS[ACTS.length-1];return a?[a.args.source,a.args.field,a.args.value].join(' '):''};
const row=()=>[...d.querySelectorAll('.ed>label')].find(l=>l.textContent==='받기')?.nextElementSibling;`;
const run = async (body) => (await cdp("Runtime.evaluate", { expression: `(async()=>{${IN}try{${body}}catch(e){return 'ERR '+e.message}})()`, awaitPromise: true, returnByValue: true })).result?.result?.value;
const res = [];
const SHOT = process.env.SHOT_DIR;   // 있으면 그림을 남김(사용자께 보일 것)
const shot = async (name) => { if (!SHOT) return; const r = await cdp("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 1100, height: 520, scale: 1 } }); fs.writeFileSync(path.join(SHOT, name), Buffer.from(r.result.data, "base64")); };
const ok = (name, cond, detail) => { res.push(!!cond); console.log((cond ? "통과 " : "실패 ") + name + (cond ? "" : " — " + JSON.stringify(detail))); };
await cdp("Emulation.setDeviceMetricsOverride", { width: 1100, height: 760, deviceScaleFactor: 1, mobile: false });
await sleep(1200);
const web = D0.sources.find((s) => s.family === "regex" && s.mode === "every" && s.rec && s.rec.length === 2) || D0.sources.find((s) => s.family === "regex" && s.mode === "every");
const W = web.id, H = web.hours, REC = web.rec.join(",");
let r = await run(`await click('[data-sel="${W}"]');const x=row();return [x.innerText.replace(/[0-9:+\\s]/g,''),!!x.querySelector('[data-follow]'),x.querySelector('[data-follow]')?.textContent,!!x.querySelector('[data-edit]'),[...d.querySelectorAll('.ed>label')].map(l=>l.textContent).join('·')]`);
await run(`const e=q('.ed [data-follow]');e.parentElement.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));return 1`);
await shot("수집창-받기.png");
ok(`받기 줄 = 되풀이 그림 + «${H}시간» 칩 + ✦ 추천 칩 + 연필 · 글자는 «시간»만 · 쪽·첨부 줄 없음`, r?.[0] === "시간" && r?.[1] && r?.[2] === web.rec.join(" ") && r?.[3] && !/첨부|쪽/.test(r?.[4]), r);
r = await run(`const n=!!q('[data-sel="${W}"] .mk');await click('.ed [data-follow="${W}"]');await w(120);return [n,last(),!q('.ed [data-follow]'),!q('[data-sel="${W}"] .mk')]`);
ok("✦ 추천 칩 = set at 추천 · 다시 그리면 ✦ 사라짐(목록 ✦ 도)", r?.[0] && r?.[1] === `${W} at ${REC}` && r?.[2] && r?.[3], r);
r = await run(`await click('[data-edit="${W}"]');await click('[data-mode="${W}"][data-v="every"]');const a=last();await w(120);await click('[data-mode="${W}"][data-v="at"]');const fo=d.activeElement===q('[data-atadd="${W}"]');await type('[data-atadd="${W}"]','9:00');return [a,fo,last()]`);
ok("연필 → 되풀이 = set hours(시각 걷음) · 바꾸기 칸은 열린 채 · 시계 = 칸에 초점 · «9:00» Enter = set at 09:00", r?.[0] === `${W} hours ${H}` && r?.[1] && r?.[2] === `${W} at 09:00`, r);
r = await run(`await w(120);await click('[data-atdel="${W}"][data-v="09:00"]');const a=last();await w(120);await click('.ed [data-edit=""]');return [a,!!q('[data-edit="${W}"]')]`);
ok("칩 × = set at 빈 값(주기로) · ✓ = 바꾸기 칸 닫힘", r?.[0] === `${W} at ` && r?.[1], r);
const M = D0.sources.find((s) => s.id === "mylms"), MD = M.rec.join() !== M.at.join();
r = await run(`await click('[data-sel="mylms"]');const x=row();return [x.querySelector('.chips')?.innerText.trim(),!!x.querySelector('[data-follow]'),x.querySelector('[data-follow]')?.textContent]`);
ok(`mylms 받기 = 크롬 그림 + 시각 칩 · ✦ 는 추천(${M.rec.join(" ")})이 지금(${M.at.join(" ")})과 다를 때만`, r?.[1] === MD && (!MD || r?.[2] === M.rec.join(" ")) && /\d\d:\d\d/.test(r?.[0] || ""), r);
r = await run(`await click('[data-edit="mylms"]');await type('[data-atadd="mylms"]','7:10');const a=last();await w(120);await click('.ed [data-follow="mylms"]');return [a,last()]`);
const M710 = [...new Set([...M.at, "07:10"])].sort().join(",");
ok(`mylms «7:10» = set mylms at ${M710} · ✦ = set mylms at 추천`, r?.[0] === `mylms at ${M710}` && r?.[1] === `mylms at ${M.rec.join(",")}`, r);
if (SHOT) { await run(`await click('[data-pop]');return 1`); await shot("수집창-톱니.png"); await run(`await click('[data-pop]');return 1`); }
r = await run(`await click('[data-pop]');const n=d.querySelectorAll('.pop .sw').length;const names=[...d.querySelectorAll('.pop > span:not(.hint)')].map(x=>x.textContent).join('·');await click('.pop [data-f="wake_pc"]');const a=last();await w(120);await click('.pop [data-f="wake"]');const b=last();return [n,names,a,b,!!q('.pop')]`);
ok("톱니 = 작은 창 네 칸(PC 깨우기·크롬 열기·자동 판정·전체) · PC 깨우기 끔 = set * wake_pc false · 크롬 열기 끔 = set mylms wake false · 창 그대로", r?.[0] === 4 && r?.[1] === "PC 깨우기·크롬 열기·자동 판정·전체" && r?.[2] === "* wake_pc false" && r?.[3] === "mylms wake false" && r?.[4], r);
r = await run(`await w(120);await click('.pop [data-f="auto_judge"]');const a=d.querySelector('.dlg p')?.textContent;d.querySelector('.dlg [data-n]')?.click();await w(60);await click('.pop [data-f="all_off"]');const b=d.querySelector('.dlg p')?.textContent;d.querySelector('.dlg [data-n]')?.click();await w(60);return [a,b]`);
ok("자동 판정 켬·전체 끔 = 묻는 창(«…켜시겠습니까?»·«모든 수집을 끄시겠습니까?»)", r?.[0]?.endsWith("켜시겠습니까?") && r?.[1] === "모든 수집을 끄시겠습니까?", r);
r = await run(`await w(120);const h=q('.pop [data-hint="wake_pc"]');const before=getComputedStyle(h.querySelector('.tip')).display;h.focus();await w(60);const after=getComputedStyle(h.querySelector('.tip')).display;return [d.querySelectorAll('.pop .hint').length,before,after,h.querySelector('.tip').innerText]`);
ok("네 칸 설명 = ? 넷 · 평소 숨김 · ? 를 누르거나 올리면 뜸(PC 깨우기 = 깨워 받음·깬 뒤 한 번)", r?.[0] === 4 && r?.[1] === "none" && r?.[2] === "block" && /잠든 PC 를 깨워/.test(r?.[3]) && /깨어난 뒤/.test(r?.[3]), r);
if (SHOT) await shot("수집창-설명.png");
r = await run(`q('.b-r').click();await w(80);return !q('.pop')`);
ok("작은 창 밖을 누르면 닫힘(일어난 일 앞)", r === true, r);
// ── 일어난 일 기록 칸(11-12 · B) — 자료 = 보기의 hist(collect_desk.py history) ──
const HS = Object.entries(D0.hist || {}).find(([k, v]) => k !== "mylms" && v.some((x) => (x.items || []).length));
if (!HS) ok("기록 있는 웹 출처", false, Object.keys(D0.hist || {}));
else {
  const [HID, HL] = HS, HI = HL.findIndex((x) => (x.items || []).length);
  r = await run(`await click('[data-sel="${HID}"]');return [d.querySelectorAll('.hs .hr').length,!!q('[data-full]')]`);
  ok(`일어난 일 = 기록 줄(8 안) + 크게 보기 단추`, r?.[0] > 0 && r?.[0] <= 8 && r?.[1], r);
  r = await run(`await click('[data-full]');const days=d.querySelectorAll('.day').length,rows=d.querySelectorAll('.hr').length;const row=[...d.querySelectorAll('.hr')].find(x=>x.querySelector('.tm').textContent===${JSON.stringify(HL[HI].t)});if(!row)return 'no row';row.click();await w(80);return [days,rows,q('.hx')?.querySelectorAll('.it').length,q('.hx')?.innerText.includes(${JSON.stringify(HL[HI].items[0].title.slice(0, 12))})]`);
  await shot("수집창-기록칸.png");
  ok(`크게 보기 = 날짜 묶음 · 줄을 누르면 그때 받은 글(${HL[HI].t})`, r?.[0] > 0 && r?.[1] > 0 && r?.[2] > 0 && r?.[3], r);
  r = await run(`await click('[data-hf="run"]');const a=d.querySelectorAll('.hr').length;await click('[data-hf="all"]');const b=d.querySelectorAll('.hr').length;await click('[data-sel="mylms"]');return [a,b,!q('.day'),!!q('.ed')]`);
  ok("거르개 받기 ≤ 전부 · 다른 출처를 고르면 상세로", r?.[0] > 0 && r?.[0] <= r?.[1] && r?.[2] && r?.[3], r);
}
chrome.kill();
console.log(`\n${res.filter(Boolean).length}/${res.length} 통과`);
process.exit(res.every(Boolean) ? 0 : 1);
