// 팝업 — 출처마다 상태 · 허용 단추(호스트 권한은 사람 손짓이 있어야 받는다 · 로그인과 같은 자리에서 사람이 정함).
const $ = (id) => document.getElementById(id);
const fmt = (ms) => (ms ? new Date(ms).toLocaleString("ko-KR") : "-");
const KEYS = { login: null, lastTick: 0, lastFullOk: 0, last: null, perm: null };

async function loadJson(f) {
  const r = await fetch(chrome.runtime.getURL(f) + "?t=" + Date.now(), { cache: "no-store" });
  if (!r.ok) throw new Error(f);
  return r.json();
}

async function sources() {
  const idx = await loadJson("ext-state.json").catch(() => ({ sources: [] }));
  const out = [];
  for (const id of idx.sources || []) {
    const k = await loadJson(`known-${id}.json`).catch(() => null);
    const host = String(((k || {}).exec || {}).host || "").replace(/\/+$/, "");
    out.push({ id, host });
  }
  return out;
}

async function show() {
  const g = await chrome.storage.local.get({ enabled: true });
  $("enabled").checked = g.enabled;
  const box = $("sources");
  const list = await sources();
  if (!list.length) return;
  box.textContent = "";
  for (const x of list) {
    const want = Object.fromEntries(Object.entries(KEYS).map(([k, v]) => [`${x.id}.${k}`, v]));
    const r = await chrome.storage.local.get(want);
    const s = Object.fromEntries(Object.keys(KEYS).map((k) => [k, r[`${x.id}.${k}`]]));
    const granted = /^https:\/\//.test(x.host) && (await chrome.permissions.contains({ origins: [x.host + "/*"] }).catch(() => false));
    const div = document.createElement("div");
    div.className = "src";
    const head = document.createElement("div");
    head.textContent = `${x.id} · ${x.host || "호스트 없음"}`;
    div.appendChild(head);
    if (!granted && /^https:\/\//.test(x.host)) {
      const b = document.createElement("button");
      b.textContent = "허용";
      const t = document.createElement("span");
      t.className = "need";
      t.textContent = " 이 사이트를 읽어도 되는지 허용이 필요합니다";
      // 권한 창은 크롬이 띄운다 — 허용하면 워커가 permissions.onAdded 로 바로 본다
      b.onclick = async () => { await chrome.permissions.request({ origins: [x.host + "/*"] }).catch(() => false); show(); };
      div.appendChild(b);
      div.appendChild(t);
    }
    const l = s.last;
    const st = (o) => (o ? o.state : "-");
    const pre = document.createElement("pre");
    pre.textContent = [
      `로그인 ${s.login === "ok" ? "됨" : s.login === "out" ? "끊김" : "-"}`,
      `마지막 확인 ${fmt(s.lastTick)}`,
      `전 단위 ${fmt(s.lastFullOk)}`,
      l ? `수집 ${fmt(l.startedAt)} (${l.why}) · 단위 ${(l.scope || []).length}` : "",
      l ? `오류 ${l.error || "없음"}` + Object.entries(l).filter(([, v]) => v && typeof v === "object" && "state" in v).map(([k, v]) => ` · ${k} ${st(v)}`).join("") : "",
    ].filter(Boolean).join("\n");
    div.appendChild(pre);
    box.appendChild(div);
  }
}

$("enabled").onchange = async () => {
  await chrome.runtime.sendMessage({ cmd: "toggle", enabled: $("enabled").checked });
};
// «수집 시작»은 워커가 메시지를 받았다는 뜻일 뿐이다 — 이미 도는 중이거나 망이 없으면 워커가 말없이 돌아선다(11-06).
// 그래서 저장소에서 실제 시작(수집 탭이 열림)을 보고 말한다. 30초 안에 안 보이면 그렇게 적는다.
const WAIT_MS = 30000, STEP_MS = 500;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
$("run").onclick = async () => {
  const b = await chrome.storage.local.get({ runningTab: null });
  $("run").disabled = true;
  $("msg").textContent = "요청함";
  await chrome.runtime.sendMessage({ cmd: "run" });
  let msg = "시작 안 됨 — 이미 도는 중이거나 망·허용이 없음 · 아래 «마지막 확인»을 본다";
  for (let t = 0; t < WAIT_MS; t += STEP_MS) {
    await sleep(STEP_MS);
    const s = await chrome.storage.local.get({ runningTab: null });
    if (s.runningTab !== null && s.runningTab !== b.runningTab) { msg = "수집 시작됨"; break; }
    if (b.runningTab !== null && s.runningTab !== null) { msg = "이미 도는 중"; break; }
  }
  $("msg").textContent = msg;
  $("run").disabled = false;
  show();
};
show();
