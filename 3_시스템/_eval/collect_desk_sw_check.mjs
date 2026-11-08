// sw.js 의 watch() 를 진짜 코드로 돌린다 — chrome·fetch 만 대역. 크롬·mylms 에 닿지 않는다. 인자 = 확장 폴더.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const DIR = process.argv[2];
const src = fs.readFileSync(path.join(DIR, "sw.js"), "utf8");
let fails = 0;
const ok = (n, c, d = "") => (console.log(`${c ? "통과" : "실패"} ${n}${c ? "" : " — " + d}`), c || fails++);

async function run(known, why, force, stored = {}) {
  const trace = [];
  const store = { enabled: true, ...stored };
  const stub = (name) =>
    new Proxy(function () {}, {
      get: (_t, k) => (k === "then" ? undefined : stub(`${name}.${String(k)}`)),
      apply: (_t, _s, args) => {
        trace.push(name);
        if (name === "chrome.storage.local.get") return Promise.resolve({ ...(args[0] || {}), ...store });
        if (name === "chrome.storage.local.set") return Object.assign(store, args[0]), Promise.resolve();
        if (name === "chrome.runtime.getURL") return "chrome-extension://x/" + args[0];
        if (name.endsWith(".addListener")) return undefined;
        return Promise.resolve([]);
      },
    });
  const fetches = [];
  const ctx = {
    chrome: stub("chrome"),
    console: { log() {}, warn() {}, error() {} },
    URL,
    URLSearchParams,
    setTimeout: (f) => (f(), 0),
    clearTimeout() {},
    self: {},
    fetch: async (u) => {
      fetches.push(String(u));
      if (String(u).includes("known.json")) return { ok: true, json: async () => known };
      return { ok: true, status: 200, url: String(u), headers: new Map(), json: async () => [], text: async () => "" };
    },
  };
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  trace.length = 0;
  fetches.length = 0;
  await vm.runInContext(`watch(${JSON.stringify(why)}, ${force ? "true" : "false"})`, ctx).catch(() => {});
  return { trace, fetches, store };
}
const base = { generatedAt: new Date().toISOString().slice(0, 19).replace("T", " "), courses: [1], knownFiles: [], board: {}, boardAt: {} };
const noWork = (r) => r.fetches.every((u) => u.includes("known.json")) && !r.trace.some((n) => /chrome\.(tabs|scripting|notifications|downloads|declarativeNetRequest)\.|chrome\.cookies\.get$/.test(n)); // cookies.getAll·set = 워커가 깰 때의 쿠키 유지(망 요청 없음 · watch 밖)

const on = await run(base, "tick");
ok("대조: 켬 = known 다음으로 일이 이어짐", !noWork(on), JSON.stringify(on.fetches));
const off = await run({ ...base, paused: true }, "tick");
ok("paused = 15분 확인이 known 에서 끝남", noWork(off), JSON.stringify([off.fetches, off.trace]));
const nav = await run({ ...base, paused: true }, "nav");
ok("paused = 페이지 이동 신호도 끝남", noWork(nav), JSON.stringify(nav.fetches));
const btn = await run({ ...base, paused: true }, "button", true);
ok("paused 라도 사람이 누른 «지금 수집»은 돈다", !noWork(btn), JSON.stringify(btn.fetches));

const quiet = { lastFullOk: Date.now(), lastRunEnd: Date.now(), probeDone: "x", lastTick: Date.now() - 900000 };
const asked = "2026-11-05T15:00:00";
const fresh = await run({ ...base, fetchNow: asked }, "tick", false, quiet);
ok("지금 받기 = 값을 기억하고 받기로 감", fresh.store.fetchNowDone === asked && !noWork(fresh), JSON.stringify(fresh.store.fetchNowDone));
const same = await run({ ...base, fetchNow: asked }, "tick", false, { ...quiet, fetchNowDone: asked });
const plain = await run(base, "tick", false, quiet);
const urls = (r) => JSON.stringify(r.fetches.map((u) => u.replace(/\?t=\d+$/, "")));
ok("같은 값은 다시 안 돈다(15분 확인과 같은 일)", urls(same) === urls(plain) && same.store.fetchNowDone === asked, urls(same) + " " + urls(plain));
const pausedAsk = await run({ ...base, fetchNow: asked, paused: true }, "tick", false, quiet);
ok("꺼져 있으면 지금 받기도 안 돈다 · 값을 안 먹는다", noWork(pausedAsk) && !pausedAsk.store.fetchNowDone, JSON.stringify(pausedAsk.store.fetchNowDone));

// 판·진입 파일 — 크롬은 진입 파일 이름이 바뀌어야 재시작 때 새 코드를 읽는다(boot 주석 · 11-05 실측)
const man = JSON.parse(fs.readFileSync(path.join(DIR, "manifest.json"), "utf8"));
const boot = man.background.service_worker;
ok("진입 파일 이름 = 판", boot === `boot-${man.version}.js`, boot);
ok("진입 파일이 있고 sw.js 를 부른다", fs.existsSync(path.join(DIR, boot)) && /importScripts\("sw\.js"\)/.test(fs.readFileSync(path.join(DIR, boot), "utf8")), boot);
process.exit(fails ? 1 : 0);
