// 확장 실행기(sw.js · 어댑터)의 watch() 를 진짜 코드로 돌린다 — chrome·fetch 만 대역. 크롬·출처 서버에 닿지 않는다. 인자 = 확장 폴더(3_시스템/collect-ext).
// 출처 = ext-state.json(id 목록) + known-<id>.json(exec · 멈춤 · 지금 받기) — PC 가 쓰는 꼴 그대로(S5).
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const DIR = process.argv[2];
const man = JSON.parse(fs.readFileSync(path.join(DIR, "manifest.json"), "utf8"));
const boot = man.background.service_worker;
const bootSrc = fs.readFileSync(path.join(DIR, boot), "utf8");
const files = [...bootSrc.matchAll(/importScripts\(([^)]*)\)/g)].flatMap((m) => [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]));
let fails = 0;
const ok = (n, c, d = "") => (console.log(`${c ? "통과" : "실패"} ${n}${c ? "" : " — " + d}`), c || fails++);
const EXT = "chrome-extension://x/";
const exec = (host, adapters = ["canvas", "learningx"]) => ({ host, adapters, run_prefix: "t-run-", raw_prefix: "t-" });

async function run(known, why, force, stored = {}, opt = {}) {
  const trace = [];
  const store = { enabled: true, ...stored };
  const stub = (name) =>
    new Proxy(function () {}, {
      get: (_t, k) => (k === "then" ? undefined : stub(`${name}.${String(k)}`)),
      apply: (_t, _s, args) => {
        trace.push(name);
        if (name === "chrome.storage.local.get") return Promise.resolve({ ...(args[0] || {}), ...store });
        if (name === "chrome.storage.local.set") return Object.assign(store, args[0]), Promise.resolve();
        if (name === "chrome.declarativeNetRequest.updateSessionRules") dnr.push(args[0]);
        if (name === "chrome.runtime.getURL") return EXT + args[0];
        if (name === "chrome.permissions.contains") return Promise.resolve(!(opt.denied || []).some((h) => args[0].origins[0].startsWith(h)));
        if (name.endsWith(".addListener")) return undefined;
        return Promise.resolve([]);
      },
    });
  const fetches = [];
  const srcs = opt.sources || { x: known };
  const ctx = {
    chrome: stub("chrome"),
    console: { log() {}, warn() {}, error() {} },
    URL,
    URLSearchParams,
    AbortSignal,
    setTimeout: (f) => (f(), 0),
    clearTimeout() {},
    self: {},
    fetch: async (u) => {
      fetches.push(String(u));
      if (String(u).startsWith(EXT + "ext-state.json")) return { ok: true, json: async () => ({ sources: Object.keys(srcs) }) };
      const m = /^chrome-extension:\/\/x\/known-([a-z0-9-]+)\.json/.exec(String(u));
      if (m) return srcs[m[1]] ? { ok: true, json: async () => srcs[m[1]] } : { ok: false };
      return { ok: true, status: 200, url: String(u), headers: new Map(), json: async () => [], text: async () => "" };
    },
  };
  ctx.self = ctx;
  ctx.importScripts = (...fs_) => { for (const f of fs_) vm.runInContext(fs.readFileSync(path.join(DIR, f), "utf8"), ctx, { filename: f }); };
  vm.createContext(ctx);
  vm.runInContext(bootSrc, ctx, { filename: boot });
  for (let i = 0; i < 50; i++) await new Promise((r) => setImmediate(r));   // 워커가 깰 때의 setup()(규칙·쿠키 유지)이 끝나게 — watch 밖
  trace.length = 0;
  fetches.length = 0;
  await vm.runInContext(`watch(${JSON.stringify(why)}, ${force ? "true" : "false"})`, ctx).catch(() => {});
  return { trace, fetches, store, dnr };
}
let dnr = [];
const base = { generatedAt: new Date().toISOString().slice(0, 19).replace("T", " "), exec: exec("https://lms.example.test"), courses: [1], knownFiles: [], board: {}, boardAt: {} };
const net = (r) => r.fetches.filter((u) => !u.startsWith(EXT));
const noWork = (r) => !net(r).length && !r.trace.some((n) => /chrome\.(tabs|scripting|notifications|downloads|declarativeNetRequest)\.|chrome\.cookies\.get$/.test(n));
const S = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => ["x." + k, v]));   // 출처 x 의 저장소 칸

ok("어댑터 둘이 등록됨(진입 파일 → 어댑터 → sw.js)", files.join() === "adapters/canvas.js,adapters/learningx.js,sw.js" || files.at(-1) === "sw.js", files.join());
dnr = [];
const on = await run(base, "tick");
ok("대조: 켬 = known 다음으로 일이 이어짐", !noWork(on), JSON.stringify(on.fetches));
const wr = on.dnr.flatMap((u) => u.addRules || []).find((r) => r.id === 9103);
ok("워커 쓰기 막기 = 조리법 호스트로 가는 GET 아닌 요청 전부(깰 때 setup)", !!wr && wr.action.type === "block" && wr.condition.regexFilter === "^https://(?:lms\\.example\\.test)/"
   && ["post", "put", "patch", "delete"].every((m) => wr.condition.requestMethods.includes(m)), JSON.stringify(wr));
ok("요청은 조리법 호스트로만", net(on).length > 0 && net(on).every((u) => u.startsWith("https://lms.example.test/")), JSON.stringify(net(on)));
const off = await run({ ...base, paused: true }, "tick");
ok("paused = 15분 확인이 known 에서 끝남", noWork(off), JSON.stringify([off.fetches, off.trace]));
const nav = await run({ ...base, paused: true }, "nav");
ok("paused = 페이지 이동 신호도 끝남", noWork(nav), JSON.stringify(nav.fetches));
const btn = await run({ ...base, paused: true }, "button", true);
ok("paused 라도 사람이 누른 «지금 수집»은 돈다", !noWork(btn), JSON.stringify(btn.fetches));

const quiet = S({ lastFullOk: Date.now(), lastRunEnd: Date.now(), probeDone: "x", lastTick: Date.now() - 900000 });
const asked = "2026-11-05T15:00:00";
const fresh = await run({ ...base, fetchNow: asked }, "tick", false, quiet);
ok("지금 받기 = 값을 기억하고 받기로 감", fresh.store["x.fetchNowDone"] === asked && !noWork(fresh), JSON.stringify(fresh.store["x.fetchNowDone"]));
const same = await run({ ...base, fetchNow: asked }, "tick", false, { ...quiet, "x.fetchNowDone": asked });
const plain = await run(base, "tick", false, quiet);
const urls = (r) => JSON.stringify(r.fetches.map((u) => u.replace(/\?t=\d+$/, "")));
ok("같은 값은 다시 안 돈다(15분 확인과 같은 일)", urls(same) === urls(plain) && same.store["x.fetchNowDone"] === asked, urls(same) + " " + urls(plain));
const pausedAsk = await run({ ...base, fetchNow: asked, paused: true }, "tick", false, quiet);
ok("꺼져 있으면 지금 받기도 안 돈다 · 값을 안 먹는다", noWork(pausedAsk) && !pausedAsk.store["x.fetchNowDone"], JSON.stringify(pausedAsk.store["x.fetchNowDone"]));

// 권한·조리법(S5) — 허용 전 출처·틀린 조리법은 요청 0 · 다른 출처는 제 호스트로만
const denied = await run(base, "tick", false, {}, { denied: ["https://lms.example.test"] });
ok("허용 전 출처 = 망 요청 0 · 저장소 perm false", !net(denied).length && denied.store["x.perm"] === false, JSON.stringify([net(denied), denied.store["x.perm"]]));
const bad = await run({ ...base, exec: exec("https://lms.example.test", ["canvas", "zz"]) }, "tick");
ok("모르는 어댑터 = 요청 0 · 까닭이 남음", !net(bad).length && /zz/.test(bad.store["x.perm"] || ""), JSON.stringify([net(bad), bad.store["x.perm"]]));
const wild = await run({ ...base, exec: exec("https://*.example.test") }, "tick");
ok("와일드카드 호스트 = 요청 0", !net(wild).length, JSON.stringify(net(wild)));
const two = await run(null, "tick", false, {}, { sources: { a: { ...base, paused: true }, b: { ...base, exec: exec("https://two.example.test", ["canvas"]) } } });
ok("출처 둘 = 멈춘 a 는 0 · b 는 제 호스트로만", net(two).length > 0 && net(two).every((u) => u.startsWith("https://two.example.test/")), JSON.stringify(net(two)));

// 판·진입 파일 — 크롬은 진입 파일 이름이 바뀌어야 재시작 때 새 코드를 읽는다(boot 주석 · 11-05 실측)
ok("진입 파일 이름 = 판", boot === `boot-${man.version}.js`, boot);
ok("진입 파일이 있고 sw.js 를 부른다", files.includes("sw.js") && files.every((f) => fs.existsSync(path.join(DIR, f))), files.join());
ok("manifest 에 호스트가 안 박힘(출처마다 허용)", !(man.host_permissions || []).length && (man.optional_host_permissions || []).length === 1, JSON.stringify(man.host_permissions));
process.exit(fails ? 1 : 0);
