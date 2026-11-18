// 외부뇌 로그인 수집기 — 서비스 워커 = 조리법을 읽는 실행기(11-16 수집 범용화 S5 · 옛 학교 전용 확장 0.3.1 을 일반화 · 동작은 그 판 그대로).
// 출처 = PC(collect-browser.py)가 이 폴더에 쓰는 ext-state.json(출처 id 목록) + known-<id>.json(조리법의 실행 칸 exec · 이미 받은 것 · 멈춤 · 지금 받기).
// 플랫폼 어댑터 = adapters/<이름>.js(워커 쪽 신호·받기 · ADAPTERS 에 등록) + adapters/<이름>-page.js(수집 탭 MAIN 세계에 넣는 받기 대본).
//   조리법은 데이터뿐 — 코드는 이 폴더의 어댑터뿐이다(MV3 는 밖에서 온 코드를 못 돌린다). 같은 플랫폼의 새 사이트 = 조리법 하나.
// 15분마다 출처마다: 권한 → 가벼운 GET 신호(로그인·지문) → 바뀐 단위만 받기 → 요약 <run_prefix><run>.json(다운로드 폴더) · 볼트 반영은 PC(collect-tick.py).
// 받기만: 수집 탭은 GET 아닌 요청을 어댑터가 밝힌 진입(allowNonGet)만 빼고, 이 워커는 출처 호스트로 가는 GET 아닌 요청을 전부 declarativeNetRequest 가 막는다(구조로 강제).
// 권한: manifest 에 호스트가 없다(optional_host_permissions) — 출처마다 팝업에서 사람이 «허용»을 누른다. 허용 전 출처는 요청 0.
// 로그인은 사람: 끊기면 알림·배지·상태 요약 한 번 → 다시 로그인하면 바로 받는다. 비밀번호를 다루는 길은 없다.
// 조리법 exec.keep_days 가 있으면 그 출처 세션 쿠키에 만료를 붙여 다시 저장한다(크롬을 닫아도 로그인이 남게 · 쿠키 값은 cookies.set 으로만 넘기고 로그·요약·저장소에 쓰지 않는다).
const TAB_BLOCK = 9101, TAB_ALLOW = 9110, WORKER_BLOCK = 9103;
const NONGET = ["post", "put", "patch", "delete"];
const TYPES = ["main_frame", "sub_frame", "xmlhttprequest", "ping", "other"];
const TICK_MIN = 15;                            // 지켜보는 간격
const MODULE_EVERY = 4;                         // 무거운 신호(단위마다 요청이 드는 것 · 모듈 목록·게시판)는 4번에 1번(1시간)
const FULL_EVERY = 12 * 3600 * 1000;            // 덮는 신호(어댑터 cover)가 안 될 때 전 단위를 받는 간격 — 게시판 글이 Canvas 만큼 온다(81 대 72 · 11-03 실측)
const FULL_EVERY_SIGNAL = 20 * 3600 * 1000;     // 덮는 신호까지 될 때의 안전망
const SIGNAL_CAP = 12;                          // 하루 신호 받기 상한 — 지문이 까닭 없이 흔들려도 서버를 두드리지 않게
const FULL_AFTER_GAP = 6 * 3600 * 1000;         // 오래 잠들었다 깨면 이만큼만 지나도 전 단위
const COOLDOWN = 30 * 60 * 1000;                // 받은 뒤 다음 받기까지 — PC 가 known 을 고칠 시간
const POLL_MS = 3000;
const PROBE_ID = "2026-11-03b";                 // 올리면 한 번 더 잰다(어댑터 probe · 쿠키 종류)
const COOKIE_QUIET = 3000;                      // 서버가 쿠키를 잇달아 바꾸는 동안은 기다린다 — 옛 값으로 덮어 로그인을 흐트러뜨리지 않게
const COOKIE_MAX_WAIT = 30000;                  // 받기처럼 쉼 없이 바뀌어도 이만큼 넘으면 저장한다
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class Net extends Error {}                      // 망·서버 문제 — 로그인 끊김이 아니다(깬 직후 Wi-Fi 없음 · 10-30 실측)
class Out extends Error {}                      // 로그인 끊김

// 저장소: 전체 칸(지켜보기 스위치·도는 탭) + 출처마다 «<id>.<칸>»(옛 판의 칸 이름 그대로 · 출처끼리 섞이지 않게)
const G_DEFAULTS = { enabled: true, runningTab: null, runningSrc: null };
const S_DEFAULTS = { last: null, lastFullOk: 0, lastRunEnd: 0, fails: 0, fp: {}, login: null, loginLog: [], lastTick: 0, tickNo: 0, retries: 0, probeDone: null, workerBlind: false, signals: {}, softFails: 0, lastNotify: 0, lastReflectAlert: 0, cache: {}, sigDay: "", sigCount: 0, loginAt: 0, pending: null, fetchNowDone: null, perm: null };
const gstate = () => chrome.storage.local.get(G_DEFAULTS);
const gput = (o) => chrome.storage.local.set(o);
const pre = (id, o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [`${id}.${k}`, v]));
async function sstate(id) {
  const r = await chrome.storage.local.get(pre(id, S_DEFAULTS));
  const out = {};
  for (const k of Object.keys(S_DEFAULTS)) out[k] = r[`${id}.${k}`];
  return out;
}
const sput = (id, o) => chrome.storage.local.set(pre(id, o));

function runId(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`;
}

// 로그인이 언제 왜 끊기는지 재는 기록 — 크롬 재시작 뒤인지, 긴 절전 뒤인지, 깨어 있는 중인지 가른다
async function note(id, ev, extra) {
  const { loginLog } = await sstate(id);
  loginLog.push({ t: Date.now(), ev, ...extra });
  await sput(id, { loginLog: loginLog.slice(-300) });
}

// ───────── 출처 읽기(PC → 확장) ─────────
const extUrl = (f) => chrome.runtime.getURL(f) + "?t=" + Date.now();
async function loadJson(f) {
  const r = await fetch(extUrl(f), { cache: "no-store" });
  if (!r.ok) throw new Error("missing " + f);
  return r.json();
}
const hostOf = (h) => { try { return new URL(h).hostname; } catch (e) { return ""; } };
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");   // declarativeNetRequest regexFilter(RE2) 용
function makeSource(id, known) {
  const e = known.exec || {};
  const host = String(e.host || "").replace(/\/+$/, "");
  const x = { id, known, host, name: e.name || id, run_prefix: e.run_prefix || `${id}-run-`, raw_prefix: e.raw_prefix || `${id}-`,
    cookieDomain: e.cookie_domain || hostOf(host), keepDays: Number(e.keep_days) || 0, tools: e.tools || {}, adapters: [], missing: [], sig: {} };
  for (const n of e.adapters || []) (self.ADAPTERS && ADAPTERS[n] ? x.adapters.push(ADAPTERS[n]) : x.missing.push(String(n)));
  x.probe = (x.adapters.find((a) => a.loginProbe) || {}).loginProbe || "";
  x.mainCookie = (x.adapters.find((a) => a.sessionCookie) || {}).sessionCookie || "";
  x.bad = !/^https:\/\/[a-z0-9.-]+(:\d+)?$/i.test(host) ? "host" : x.missing.length ? "adapter " + x.missing.join(",") : !x.probe ? "no_probe" : "";
  return x;
}
let cached = [];                                // 마지막으로 읽은 출처 — 쿠키·알림 처리가 파일을 또 읽지 않게(없으면 읽는다)
async function loadSources() {
  const idx = await loadJson("ext-state.json");
  const out = [];
  for (const id of idx.sources || []) {
    if (!/^[a-z0-9][a-z0-9-]{0,48}$/.test(String(id))) continue;
    try { out.push(makeSource(id, await loadJson(`known-${id}.json`))); } catch (e) { out.push({ id, bad: "known_missing", adapters: [], sig: {} }); }
  }
  cached = out;
  return out;
}
const sourcesNow = async () => (cached.length ? cached : loadSources().catch(() => []));

// 워커 자신의 GET 아닌 요청 막기 — 출처 호스트 전부(허용 전 출처 포함 · 막기는 해가 없다)
let guarded = null;
async function guardWorker(list) {
  const hosts = list.filter((x) => x.host && !x.bad).map((x) => esc(x.host.replace(/^https:\/\//, ""))).sort();
  const key = hosts.join("|");
  if (key === guarded) return;
  await chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [WORKER_BLOCK],
    addRules: hosts.length ? [{ id: WORKER_BLOCK, priority: 1, action: { type: "block" },
      condition: { tabIds: [chrome.tabs.TAB_ID_NONE], requestMethods: NONGET, resourceTypes: ["xmlhttprequest", "other"], regexFilter: `^https://(?:${key})/` } }] : [],
  });
  guarded = key;
}

async function setup() {
  const a = await chrome.alarms.get("tick");
  if (!a || a.periodInMinutes !== TICK_MIN) await chrome.alarms.create("tick", { delayInMinutes: 1, periodInMinutes: TICK_MIN });
  const list = await loadSources().catch(() => []);
  await guardWorker(list).catch(() => {});
  await keepCookies(list);                      // 워커가 깰 때마다 — 사람이 이미 로그인해 둔 세션 쿠키·놓친 변경을 잡는다
}

chrome.runtime.onInstalled.addListener(() => setup());
chrome.runtime.onStartup.addListener(async () => {
  for (const x of await sourcesNow()) if (!x.bad) { await note(x.id, "startup", await cookieBrief(x)); await sput(x.id, { pending: { after: "startup" } }); }
  await setup();
});
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "tick" || a.name === "retry") watch(a.name); });
chrome.permissions.onAdded.addListener(() => watch("perm"));   // 팝업에서 허용하면 바로 본다
chrome.runtime.onMessage.addListener((m, _s, reply) => {
  if (m && m.cmd === "run") { watch("button", true); reply({ ok: true }); }
  if (m && m.cmd === "toggle") { gput({ enabled: !!m.enabled }).then(() => reply({ ok: true })); return true; }
});
chrome.notifications.onClicked.addListener(async (id) => {
  const [kind, sid] = id.split(":");
  const x = (await sourcesNow()).find((s) => s.id === sid);
  // active 는 창을 앞으로 가져오지 않는다 — 최소화 창이면 눌러도 아무 일 없어 보인다
  const url = kind === "login" && x && x.host ? x.host + "/" : kind === "perm" ? chrome.runtime.getURL("popup.html") : null;
  if (url) chrome.tabs.create({ url, active: true }).then((t) => chrome.windows.update(t.windowId, { focused: true })).catch(() => chrome.windows.create({ url, focused: true }));
  chrome.notifications.clear(id);
});

// ───────── 로그인 유지 ─────────
// Canvas 쿠키는 전부 세션 쿠키다(11-03 실측) — 크롬을 닫으면 사라진다(재부팅 30일 33회). 서버가 다시 줄 때마다 세션 쿠키로 돌아가므로 바뀔 때마다 다시 붙인다.
// 그 출처 도메인 쿠키만: 이름이 같아도 상위 도메인 쿠키는 건드리지 않는다. 사라진 쿠키는 되살리지 않는다(로그아웃을 존중). 서버가 만료를 정한 쿠키도 그대로 둔다.
const mine = (x, c) => c.domain.replace(/^\./, "") === x.cookieDomain;
const cookieList = async (x) => (await chrome.cookies.getAll({ domain: x.cookieDomain }).catch(() => [])).filter((c) => mine(x, c));
const keepFailed = new Set();
async function keepCookies(list) {
  if (!(await gstate()).enabled) return;
  for (const x of list || (await sourcesNow())) {
    if (x.bad || !x.keepDays) continue;
    const exp = Math.floor(Date.now() / 1000) + x.keepDays * 86400;
    for (const c of await cookieList(x)) {     // 바로 앞에서 읽은 값으로 — 이벤트가 전한 값을 쓰면 그 사이 서버가 준 새 값을 덮는다
      if (!c.session) continue;
      const d = { url: `https://${x.cookieDomain}${c.path}`, name: c.name, value: c.value, path: c.path, secure: c.secure, httpOnly: c.httpOnly, sameSite: c.sameSite, expirationDate: exp, storeId: c.storeId };
      if (!c.hostOnly) d.domain = c.domain;
      if (c.partitionKey) d.partitionKey = c.partitionKey;
      const r = await chrome.cookies.set(d).catch(() => null);
      lastOwn = Date.now();
      if (!r && !keepFailed.has(x.id + c.name)) { keepFailed.add(x.id + c.name); await note(x.id, "keep_fail", { name: c.name }); }
    }
  }
}
// 쿠키 사건은 허용한 호스트 것만 온다(= 출처). 세션 쿠키가 바뀌면 만료를 다시 붙이고, 끊긴 출처가 있으면 바로 다시 본다(사람이 로그인한 직후 · 옛 판의 «페이지 열림» 신호 대신 —
// 그것은 호스트를 모르는 채 모든 https 이동에 워커를 깨웠다). 내 요청이 받아 온 쿠키(끊긴 동안 서버가 주는 익명 세션 등)로는 안 깨운다 — 내 일 뒤 10초 · 20초에 한 번.
let cookieTimer = null, cookieFirst = 0, lastNav = 0, lastOwn = 0;
chrome.cookies.onChanged.addListener(({ removed }) => {
  if (removed) return;
  const now = Date.now();
  if (!cookieTimer) cookieFirst = now;
  clearTimeout(cookieTimer);
  cookieTimer = setTimeout(async () => {
    cookieTimer = null;
    const list = await sourcesNow();
    await keepCookies(list);
    if (busy || Date.now() - lastOwn < 10000 || Date.now() - lastNav < 20000) return;
    for (const x of list) if (!x.bad && (await sstate(x.id)).login !== "ok") { lastNav = Date.now(); watch("nav"); break; }
  }, now - cookieFirst > COOKIE_MAX_WAIT ? 0 : COOKIE_QUIET);
});
// 이름·종류만 — 값은 버린다. 끊겼을 때 이것으로 «서버 쪽 세션이 끝남»과 «브라우저가 쿠키를 잃음»을 가른다
async function cookieBrief(x) {
  const list = await cookieList(x);
  return { cookies: list.length, session: list.filter((c) => c.session).length, main: !!x.mainCookie && list.some((c) => c.name === x.mainCookie) };
}

setup();

async function notify(id, title, message) {
  try { await chrome.notifications.create(id, { type: "basic", iconUrl: "icon.png", title, message }); } catch (e) {}
}
const marks = {};                               // 출처마다 배지 표시 — 끊김(!)이 허용 필요(?)보다 앞
function mark(id, m) {
  marks[id] = m;
  const v = Object.values(marks);
  chrome.action.setBadgeText({ text: v.includes("!") ? "!" : v.includes("?") ? "?" : "" }).catch(() => {});
}

// 탭이 없어도(로그인 끊김) 요약이 PC 로 간다 — 0.1.x 는 끊긴 8회가 대기열에 한 줄도 안 남았다(10-27~11-03 실측)
async function saveJson(x, obj) {
  const url = "data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(obj));
  await chrome.downloads.download({ url, filename: `${x.run_prefix}${obj.run}.json`, conflictAction: "uniquify", saveAs: false });
}

// ───────── 가벼운 확인(GET 만) — 어댑터가 x.getJson·x.getAuth 로 부른다 ─────────
// 끊김은 로그인 탐침(어댑터 loginProbe)만 판정한다 — Canvas 는 권한 없는 강좌에도 401 을 준다. 그 밖의 길은 안 되면 그 신호만 빠진다(null).
const alive = () => chrome.runtime.getPlatformInfo();  // 워커 유휴 타이머(30초)를 되돌린다 — fetch 만 잇달면 잘릴 수 있다
function tools(x) {
  x.getJson = async (path, strict, kind) => {
    const out = [];
    let url = x.host + path;
    for (let i = 0; url && i < 5; i++) {        // 다음 쪽(Link) — 빠진 뒤쪽 글을 «변화 없음»으로 보지 않게
      let r;
      await alive();
      try {
        r = await fetch(url, { credentials: "include", cache: "no-store", redirect: "manual", headers: { Accept: "application/json" }, signal: AbortSignal.timeout(25000) });
      } catch (e) {
        if (kind) x.sig[kind] = "net";
        if (strict) throw new Net(String(e.message || e));
        return null;                            // 그 신호만 빠진다 — 한 길의 장애가 로그인 판정·안전망을 세우지 않게
      }
      const code = r.type === "opaqueredirect" ? "redirect" : r.status;
      if (kind) x.sig[kind] = code;
      if (code !== 200) {
        if (!strict) return null;
        // 끊김 = 401·돌림·404(비로그인 users/self = 404 · 10-25 실측) — 처음이면 watch 가 탭으로 한 번 더 본다 · 403·429·5xx 는 판단 보류
        if (code === 401 || code === 404 || code === "redirect") throw new Out("login_required");
        throw new Net("status " + code);
      }
      let j;
      try { j = JSON.parse((await r.text()).replace(/^while\(1\);/, "")); } catch (e) {
        if (strict) throw new Net("not_json");  // 점검 화면 등 — 로그인 됨으로 치지 않는다
        return null;
      }
      if (!Array.isArray(j)) return j;
      out.push(...j);
      const m = /<([^>]+)>;\s*rel="next"/.exec(r.headers.get("Link") || "");
      url = m ? m[1] : null;
    }
    return out;
  };
  x.getAuth = async (path, token, kind) => {    // 쿠키 + Bearer(페이지가 얻는 토큰 · 어댑터가 쿠키에서 읽어 넘긴다)
    await alive();
    let r;
    try {
      r = await fetch(x.host + path, { credentials: "include", cache: "no-store", redirect: "manual", headers: { Accept: "application/json", Authorization: "Bearer " + token }, signal: AbortSignal.timeout(25000) });
    } catch (e) { x.sig[kind] = "net"; return null; }
    x.sig[kind] = r.type === "opaqueredirect" ? "redirect" : r.status;
    if (r.status !== 200) return null;
    try { return await r.json(); } catch (e) { return null; }
  };
  x.cookie = (name) => chrome.cookies.get({ url: x.host + "/", name }).catch(() => null);
  x.probeOne = async (out, name, path, headers) => {   // 탐침 — 내용은 남기지 않고 상태·개수·칸 이름만
    try {
      await alive();
      const r = await fetch(x.host + path, { credentials: "include", cache: "no-store", redirect: "manual", headers: { Accept: "application/json", ...headers }, signal: AbortSignal.timeout(25000) });
      const text = r.type === "opaqueredirect" ? "" : await r.text();
      let j = null;
      try { j = JSON.parse(text.replace(/^while\(1\);/, "")); } catch (e) {}
      const rows = Array.isArray(j) ? j : j && Array.isArray(j.items) ? j.items : null;
      const first = rows ? rows[0] : j;
      out[name] = { status: r.status, type: r.type, bytes: text.length, n: rows ? rows.length : null, keys: first && typeof first === "object" ? Object.keys(first).slice(0, 40) : null };
      return j;
    } catch (e) { out[name] = { error: String(e.message || e) }; return null; }
  };
  x.hash = hash;
  x.hashOf = hashOf;
  x.inMain = inMain;
  x.fileInMain = fileInMain;
  x.poll = poll;
  return x;
}

function hash(s) {                              // FNV-1a — 바뀌었는지만 본다
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return (h >>> 0).toString(36);
}
const hashOf = (list) => hash(list.sort().join("\n"));

// 단위(과목)마다 지문 — 어댑터가 칸을 채운다(Canvas a 공지·p 할 일·m 모듈 · LearningX b 게시판). 가벼운 신호는 매번, 무거운 신호는 heavy 일 때만.
async function snapshot(x, units, prev, heavy, cache, fresh) {
  const me = await x.getJson(x.probe, true, "me");    // 로그인 확인 + 세션 유지
  if (!me || !me.id) throw new Net("no_id");
  const out = {};
  for (const c of units) out[c] = { ...(prev[c] || {}) };
  for (const a of x.adapters) if (a.signals) await a.signals(x, units, out);
  if (heavy) {
    const next = { ...cache };
    for (const a of x.adapters) if (a.heavy) next[a.slot] = await a.heavy(x, units, out, fresh ? {} : cache[a.slot] || {});
    await sput(x.id, { cache: next });
  }
  return out;
}

const changedOf = (units, prev, cur) => units.filter((c) => {
  const a = prev[c], b = cur[c];
  if (!a) return false;                         // 첫 기준 — 바뀐 것이 아니다
  return Object.keys(b).some((k) => a[k] !== undefined && b[k] !== undefined && a[k] !== b[k]);
});

async function setLogin(x, login, s, extra) {
  if (s.login === login) return;
  await sput(x.id, { login, ...(login === "ok" ? { loginAt: Date.now() } : {}) });
  await note(x.id, "login", { login, ...extra });
  mark(x.id, login === "out" ? "!" : "");
  if (login === "out") await notify("login:" + x.id, "외부뇌 수집", `${x.id} 로그인 필요`);
  else await chrome.notifications.clear("login:" + x.id).catch(() => {});
  if (s.login !== null || login === "out") await saveJson(x, { kind: "status", source: x.id, login, run: runId(new Date()), at: Date.now(), version: chrome.runtime.getManifest().version, loginLog: (await sstate(x.id)).loginLog.slice(-40) }).catch(() => {});
}

// ───────── 지켜보기 ─────────
let busy = false;
async function watch(why, force) {
  if (busy) return;
  busy = true;
  try {
    const g = await gstate();
    if (!g.enabled && !force) return;
    if (g.runningTab) {                         // 워커가 받기 도중 죽어 남은 탭
      await chrome.tabs.remove(g.runningTab).catch(() => {});
      await gput({ runningTab: null, runningSrc: null });
      if (g.runningSrc) await note(g.runningSrc, "orphan");
    }
    const list = await loadSources();
    await guardWorker(list);
    for (const x of list) {
      try { await watchOne(tools(x), why, force); } catch (e) { await note(x.id, "error", { error: String(e.message || e) }).catch(() => {}); }
    }
  } catch (e) {
    mark("_", "?");                             // ext-state.json 이 없거나 깨짐 — PC 반영이 아직 안 씀
  } finally {
    busy = false;
    lastOwn = Date.now();
  }
}

async function watchOne(x, why, force) {
  if (x.bad) { await sput(x.id, { perm: "bad:" + x.bad }); return; }   // 조리법 칸이 틀림(호스트·어댑터) — 요청 0
  const s = await sstate(x.id);
  if (!(await chrome.permissions.contains({ origins: [x.host + "/*"] }).catch(() => false))) {
    if (s.perm !== false) { await sput(x.id, { perm: false }); await notify("perm:" + x.id, "외부뇌 수집", `${x.id} 허용 필요 — 눌러서 허용`); }
    mark(x.id, "?");
    return;                                     // 허용 전 = 요청 0
  }
  if (s.perm !== true) { await sput(x.id, { perm: true }); mark(x.id, s.login === "out" ? "!" : ""); }
  const now = Date.now();
  let pending = s.pending;                      // 재시작·긴 틈 뒤 첫 확인 — 로그인이 그것을 넘겼는지 남긴다(세션 수명의 재료)
  if (s.lastTick && now - s.lastTick > 2.5 * TICK_MIN * 60000) {
    const min = Math.round((now - s.lastTick) / 60000);
    await note(x.id, "gap", { min });
    pending = { after: pending ? pending.after : "gap", min };
    await sput(x.id, { pending });
  }
  const tickNo = s.tickNo + 1;
  await sput(x.id, { lastTick: now, tickNo });

  const known = x.known;
  if (known.paused && !force) return;           // 수집 창에서 끔 · 사람이 누른 «지금 수집»은 돈다
  if (known.fetchNow && known.fetchNow !== s.fetchNowDone) {   // 수집 창 «지금 받기» — 누른 값 하나에 한 번만
    await sput(x.id, { fetchNowDone: known.fetchNow });
    force = true;
    why = "desk";
  }
  const units = (known.courses || []).map(String);
  // PC 쪽 반영이 멈춘 것을 여기서 잡는다 — known 은 반영할 때마다 새로 써진다. 막 깬 때는 PC 예약도 아직 안 돌았으니 뺀다
  const knownAge = known.generatedAt ? now - Date.parse(known.generatedAt.replace(" ", "T")) : 0;
  if (knownAge > 2 * 3600 * 1000 && s.lastTick && now - s.lastTick < 30 * 60 * 1000 && now - s.lastReflectAlert > 24 * 3600 * 1000) {
    await sput(x.id, { lastReflectAlert: now });
    await notify("reflect:" + x.id, "외부뇌 수집", "PC 반영 멈춤");
  }
  let cur = null, blind = false;
  try {
    // 무거운 신호의 목록(게시판 번호 등)은 하루에 한 번 새로 — 새 게시판을 놓치지 않게
    cur = await snapshot(x, units, s.fp, tickNo % MODULE_EVERY === 1 || !Object.keys(s.fp).length, s.cache, tickNo % 96 === 1);
  } catch (e) {
    if (e instanceof Net) {                     // 깬 직후엔 망이 아직 없다 — 1분 뒤 다시(다섯 번까지)
      if (s.retries < 5) { await sput(x.id, { retries: s.retries + 1 }); await chrome.alarms.create("retry", { delayInMinutes: 1 }); }
      else await sput(x.id, { retries: 0 });
      return;
    }
    if (!(e instanceof Out)) throw e;
    // 워커의 401 만 믿으면 쿠키가 안 실리는 경우와 끊김을 못 가른다 — 처음 끊겨 보일 때 탭으로 한 번 더 본다. 버튼은 탭 쪽 확인에 맡긴다
    const had = await cookieBrief(x);           // 탭을 열기 전에 — 탭이 쿠키를 바꿀 수 있다
    blind = s.login !== "out" && !(await tabSaysOut(x).catch(() => true));
    if (!blind && !force) {
      await setLogin(x, "out", s, { ...had, ...pending, aliveMin: s.loginAt ? Math.round((now - s.loginAt) / 60000) : null });
      await sput(x.id, { pending: null });
      if (s.login === "out" && now - s.lastNotify > 6 * 3600 * 1000) { await sput(x.id, { lastNotify: now }); await notify("login:" + x.id, "외부뇌 수집", `${x.id} 로그인 필요`); }   // 빈방에 울리고 끝나지 않게 — 여섯 시간마다
      return;
    }
    if (blind) await note(x.id, "worker401");
  }
  const signals = { ...s.signals, ...x.sig };
  await sput(x.id, { retries: 0, workerBlind: blind, signals });
  if (cur || blind) {
    if (s.login === "out") { s.fails = 0; s.lastRunEnd = 0; await sput(x.id, { fails: 0, lastRunEnd: 0 }); }   // 다시 로그인했으면 물림 없이 바로 받는다
    await setLogin(x, "ok", s);
    if (pending) {
      if (s.login === "ok") await note(x.id, "survived", pending);
      await sput(x.id, { pending: null });
    }
  }

  const changed = cur ? changedOf(units, s.fp, cur) : [];
  const backoff = Math.min(2 ** s.fails * COOLDOWN, 6 * 3600 * 1000);
  const cool = now - s.lastRunEnd < (s.fails ? backoff : COOLDOWN);
  const longGap = s.lastTick && now - s.lastTick > 6 * 3600 * 1000;
  const covered = x.adapters.every((a) => !a.cover || signals[a.cover] === 200);
  const day = new Date(now).toDateString();
  const sigCount = s.sigDay === day ? s.sigCount : 0;
  let job = null;
  if (force) job = { why, units };
  else if (now - s.lastFullOk > (longGap ? FULL_AFTER_GAP : covered ? FULL_EVERY_SIGNAL : FULL_EVERY) && !cool) job = { why: "daily", units, probe: s.probeDone !== PROBE_ID };
  else if (changed.length && !cool && sigCount < SIGNAL_CAP) job = { why: "signal", units: changed };
  else if (s.probeDone !== PROBE_ID && !cool) job = { why: "probe", units: units.slice(0, 1), probe: true };

  // 받기로 한 단위와 바뀌지 않은 단위는 기준을 지금 값으로, 받지 못한 변경은 다음에 다시 보이게 둔다
  if (cur) {
    const fp = { ...s.fp };
    for (const c of units) if (!changed.includes(c)) fp[c] = cur[c];
    await sput(x.id, { fp });
  }
  if (!job) return;

  // 착수 기록 — 받기 도중 워커가 죽어도 쉼·실패가 남아 15분마다 전 단위를 다시 받지 않는다
  await sput(x.id, { lastRunEnd: Date.now(), fails: s.fails + 1, sigDay: day, sigCount: sigCount + (job.why === "signal" ? 1 : 0) });
  const sum = await collect(x, job);
  // 어댑터의 부분 오류(게시판 과목 하나 등)는 대기열·알림으로만 — ok 에 섞으면 고장 난 동안 전 단위 받기가 되풀이된다
  const softBad = x.adapters.filter((a) => a.softBad && a.softBad(sum[a.slot]));
  const softFails = softBad.length ? s.softFails + 1 : 0;
  const ok = !sum.error && x.adapters.every((a) => !a.collect || (sum[a.slot] || {}).state === "done");
  const after = { lastRunEnd: Date.now(), fails: ok ? 0 : s.fails + 1, last: sum, softFails };
  if (softFails === 3) await notify("fail:" + x.id, "외부뇌 수집", `${x.id} ${softBad.map((a) => a.label || a.slot).join("·")} 연달아 실패`);
  if (ok) {
    if (cur) {
      const f2 = (await sstate(x.id)).fp;
      for (const c of job.units) f2[c] = cur[c];
      after.fp = f2;
    }
    if (job.units.length === units.length) after.lastFullOk = sum.startedAt;
    if (job.probe) after.probeDone = PROBE_ID;
  }
  await sput(x.id, after);
  if (sum.error === "login_required") await setLogin(x, "out", await sstate(x.id), await cookieBrief(x));
  else if (!ok && after.fails === 3) await notify("fail:" + x.id, "외부뇌 수집", `${x.id} 연달아 실패 · ${sum.error || x.adapters.filter((a) => a.collect).map((a) => `${a.slot} ${(sum[a.slot] || {}).state}`).join(" · ")}`);
}

// ───────── 받기(탭 안에서) ─────────
function waitComplete(tabId, ms = 60000) {
  return new Promise((resolve) => {
    const t0 = Date.now();
    const tick = async () => {
      const tab = await chrome.tabs.get(tabId).catch(() => null);
      if (!tab) return resolve(null);
      // about:blank 에서 떠난 뒤의 complete 만(빈 문서의 complete 를 잡는 실수 — 게시판 대본과 같은 함정)
      if (tab.status === "complete" && tab.url !== "about:blank") return resolve(tab);
      if (Date.now() - t0 > ms) return resolve(tab);
      setTimeout(tick, 500);
    };
    tick();
  });
}

const inMain = (tabId, func, args = []) =>
  chrome.scripting.executeScript({ target: { tabId }, world: "MAIN", func, args }).then((r) => r[0] && r[0].result);
const fileInMain = (tabId, file) => chrome.scripting.executeScript({ target: { tabId }, world: "MAIN", files: [file] });

// 숨은 탭은 크롬이 페이지 타이머를 늦춘다(5분 뒤엔 1분에 한 번). 대본의 대기를 페이지 타이머 대신
// 서비스 워커가 250ms 마다 깨운다 — executeScript 는 늦춰지지 않는다(10-26 실수집에서 게시판 단계가 1분 단위로 늘어짐).
const PUMP_SETUP = () => {
  if (window.__collectSleep) return;
  const q = [];
  window.__collectSleep = (ms) => new Promise((r) => q.push({ t: Date.now() + ms, r }));
  window.__collectPump = () => {
    const now = Date.now();
    for (const x of q.filter((y) => y.t <= now)) { q.splice(q.indexOf(x), 1); x.r(); }
  };
};

async function poll(tabId, kind, ms) {
  const t0 = Date.now();
  let last = 0;
  while (Date.now() - t0 < ms) {
    await sleep(250);
    await inMain(tabId, () => window.__collectPump && window.__collectPump()).catch(() => {});
    if (Date.now() - last < POLL_MS) continue;
    last = Date.now();
    const st = await inMain(tabId, () => { const c = window.__collect; return c ? { kind: c.kind, state: c.state, result: c.result || null, results: c.results || null, log: (c.log || []).slice(-3) } : null; }).catch((e) => ({ state: "error", result: { error: String(e) } }));
    if (st && st.kind === kind && st.state !== "running") return st;
    if (st && st.state === "error") return st;
  }
  return { kind, state: "timeout" };
}

// 수집 탭이 보낸 요청을 센다 — 주소는 쿼리 값을 버리고 숫자 경로를 N 으로 접는다(토큰·글 번호가 남지 않게). 허용한 호스트 요청만 보인다.
function watchRequests(x, tabId, probe) {
  const rec = { get: 0, other: {}, blocked: {}, shapes: {}, headers: {} };
  const shape = (d) => {
    try {
      const u = new URL(d.url);
      const q = [...new Set(u.searchParams.keys())].sort().join("&");
      return `${d.method} ${u.origin}${u.pathname.replace(/\/\d+(?=\/|$)/g, "/N")}${q ? "?" + q : ""} [${d.type}]`;
    } catch (e) { return `${d.method} ? [${d.type}]`; }
  };
  const key = (d) => shape(d).replace(/\?[^ ]*/, "");
  const onReq = (d) => {
    if (d.method === "GET") {
      rec.get++;
      if (probe && d.url.startsWith(x.host + "/") && d.type === "xmlhttprequest") rec.shapes[shape(d)] = (rec.shapes[shape(d)] || 0) + 1;
    } else rec.other[key(d)] = (rec.other[key(d)] || 0) + 1;
  };
  const onErr = (d) => { if (d.error === "net::ERR_BLOCKED_BY_CLIENT") rec.blocked[key(d)] = (rec.blocked[key(d)] || 0) + 1; };
  const onHead = (d) => { for (const h of d.requestHeaders || []) if (!/^(sec-|accept|user-agent|referer|cookie)/i.test(h.name)) rec.headers[h.name] = (rec.headers[h.name] || 0) + 1; };   // 이름만
  const filter = { urls: ["<all_urls>"], tabId };
  chrome.webRequest.onBeforeRequest.addListener(onReq, filter);
  chrome.webRequest.onErrorOccurred.addListener(onErr, filter);
  if (probe) chrome.webRequest.onSendHeaders.addListener(onHead, { urls: [x.host + "/*"], tabId }, ["requestHeaders"]);
  return () => {
    chrome.webRequest.onBeforeRequest.removeListener(onReq);
    chrome.webRequest.onErrorOccurred.removeListener(onErr);
    chrome.webRequest.onSendHeaders.removeListener(onHead);
    return rec;
  };
}

// 수집 탭: GET 아닌 요청은 어댑터가 밝힌 진입(allowNonGet · 그 출처 호스트 안)만 통과 — 나머지는 어느 주소로든 막힌다
async function guard(x, tabId, on) {
  const allow = [...new Set(x.adapters.flatMap((a) => a.allowNonGet || []))].slice(0, 9);
  await chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [TAB_BLOCK, ...Array.from({ length: 9 }, (_, i) => TAB_ALLOW + i)],
    addRules: on ? [
      ...allow.map((p, i) => ({ id: TAB_ALLOW + i, priority: 2, action: { type: "allow" },
        condition: { tabIds: [tabId], requestMethods: NONGET, resourceTypes: TYPES, regexFilter: "^" + esc(x.host + p) } })),
      { id: TAB_BLOCK, priority: 1, action: { type: "block" },
        condition: { tabIds: [tabId], requestMethods: NONGET, resourceTypes: TYPES, regexFilter: "^https?://" } },
    ] : [],
  });
}

// 창이 하나도 없는 크롬(예약 깨기로 띄움)에서는 탭을 못 연다 — 최소화 창을 만들고 끝나면 닫는다
async function openTab() {
  try {
    const tab = await chrome.tabs.create({ url: "about:blank", active: false });
    return { tabId: tab.id, windowId: null };
  } catch (e) {
    const w = await chrome.windows.create({ url: "about:blank", focused: false, state: "minimized" });
    return { tabId: w.tabs[0].id, windowId: w.id };
  }
}

// 워커가 401 을 받았을 때 진짜 끊겼는지 탭으로 본다 — 탭은 평소 받기와 같은 길이고 쓰기는 막혀 있다
async function tabSaysOut(x) {
  const { tabId, windowId } = await openTab();
  try {
    await guard(x, tabId, true);
    await chrome.tabs.update(tabId, { url: x.host + "/" });
    const t = await waitComplete(tabId, 30000);
    if (!t || !(t.url || "").startsWith(x.host)) return true;
    return (await inMain(tabId, async (p) => (await fetch(p, { credentials: "include" })).status, [x.probe])) !== 200;
  } finally {
    await guard(x, tabId, false).catch(() => {});
    await chrome.tabs.remove(tabId).catch(() => {});
    if (windowId !== null) await chrome.windows.remove(windowId).catch(() => {});
  }
}

async function cookieMeta(x) {   // 값은 읽어 버린다 — 이름·종류·만료만
  const list = await chrome.cookies.getAll({ url: x.host + "/" }).catch(() => []);
  return list.map((c) => ({ name: c.name, domain: c.domain, session: c.session, exp: c.expirationDate || null, httpOnly: c.httpOnly }));
}

async function collect(x, job) {
  const started = new Date();
  const summary = { kind: "run", source: x.id, run: runId(started), why: job.why, scope: job.units.map(Number), startedAt: started.getTime(), version: chrome.runtime.getManifest().version, error: null };
  x.run = summary.run;
  let tabId = null, windowId = null, stopWatch = null;
  try {
    // 빈 탭을 먼저 열어 요청 관찰·차단 규칙을 건 뒤에 출처로 간다(첫 요청부터 잡히게)
    ({ tabId, windowId } = await openTab());
    await gput({ runningTab: tabId, runningSrc: x.id });
    stopWatch = watchRequests(x, tabId, job.probe);
    await guard(x, tabId, true);
    await chrome.tabs.update(tabId, { url: x.host + "/" });
    const t = await waitComplete(tabId);
    if (!t) throw new Error("tab_closed");
    if (t.status !== "complete") throw new Error("net_timeout");
    if (!(t.url || "").startsWith(x.host)) throw new Error("login_required");
    const me = await inMain(tabId, async (p) => (await fetch(p, { credentials: "include" })).status, [x.probe]);
    if (me !== 200) throw new Error(me === 401 || me === 404 ? "login_required" : "api_" + me);

    await inMain(tabId, PUMP_SETUP);
    for (const a of x.adapters) {               // 조리법의 어댑터 차례대로 — 앞 어댑터가 로그인 끊김을 보면 멈춘다
      if (!a.collect) continue;
      summary[a.slot] = await a.collect(x, tabId, job);
      if (summary[a.slot] && summary[a.slot].result && summary[a.slot].result.error === "login_required") throw new Error("login_required");
    }
    if (job.probe) {
      summary.probe = {};
      for (const a of x.adapters) if (a.probe) await a.probe(x, job.units[0], summary.probe);
    }
  } catch (e) {
    const msg = String(e.message || e);
    summary.error = /error page|ERR_|Failed to fetch|^net_/.test(msg) ? "net" : msg;
  }
  for (const a of x.adapters) if (a.after) await a.after(x, job, summary).catch(() => {});   // 받기가 실패해도 본다(과목 지도 낡음 등)
  // 첨부가 다 내려온 뒤에 요약을 쓴다 — PC 가 요약을 먼저 집으면 받는 중인 첨부를 «없음»으로 본다(큰 파일 · 상한 10분)
  for (let t0 = Date.now(); Date.now() - t0 < 10 * 60 * 1000; await sleep(2000)) {
    const left = await chrome.downloads.search({ state: "in_progress" }).catch(() => []);
    if (!left.length) break;
    summary.downloadsWaited = Math.round((Date.now() - t0) / 1000);
  }
  summary.endedAt = Date.now();
  if (stopWatch) summary.requests = stopWatch();
  const st = await sstate(x.id);
  summary.loginLog = st.loginLog.slice(-40);
  summary.cookies = await cookieMeta(x);        // 이름·종류·만료만 — 만료가 붙어 있는지(session: false) 여기서 본다
  summary.signals = st.signals;
  summary.workerBlind = st.workerBlind;
  await saveJson(x, summary).catch(() => {});
  await sleep(3000);
  if (tabId !== null) { await guard(x, tabId, false).catch(() => {}); await chrome.tabs.remove(tabId).catch(() => {}); }
  if (windowId !== null) await chrome.windows.remove(windowId).catch(() => {});
  await gput({ runningTab: null, runningSrc: null });
  return summary;
}
