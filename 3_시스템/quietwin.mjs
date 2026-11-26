// 시험이 창을 띄울 때 쓰는 공통 부품(ADR-044). child_process.spawn 과 같은 꼴이고 창만 사용자 화면 밖에 뜬다.
//   import { spawnQuiet } from "file:///<볼트>/3_시스템/quietwin.mjs";
// BRAIN_SHOW_WINDOW=1 = 사람이 보려고 일부러 띄울 때만.
// 격리 옵시디언(Obsidian.exe --user-data-dir=…)은 띄우기 전에 링크 파이프 주인을 잰다(obs_pipe.py · 11-23 사고
// incident-2026-11-23-볼트링크-시험옵시디언이-cli파이프-쥠): 옵시디언 1.15 는 링크를 OS 사용자당 하나뿐인 파이프로 넘기고 먼저 뜬 창이 쥔다 —
// 사용자 옵시디언이 꺼진 채 시험 창이 뜨면 시험 창이 쥐어, 뒤에 켠 사용자 옵시디언엔 링크가 안 온다. 주인이 없으면 곧바로 오류(기다리지 않음).
import { execFileSync, spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const HELPER = path.join(HERE, "quietwin.py");
const OBS_PIPE = path.join(HERE, "obs_pipe.py");
// 화면 밖 데스크톱엔 수직 동기 신호가 없어 그리기가 초당 13번으로 떨어진다(11-05 실측 · 이 인자로 150).
const CHROMIUM = /obsidian|chrome|msedge|electron/i;

/** 격리 옵시디언을 띄워도 되나 — 링크 파이프 주인이 없으면(사용자 옵시디언 꺼짐) 던진다 · 잼 실패는 막지 않음 */
export function obsGuard(exe, args = []) {
  if (!/^obsidian\.exe$/i.test(path.basename(exe))) return;
  const a = args.map(String);
  if (!a.some((x) => x.startsWith("--user-data-dir"))) return; // 시험 틀은 늘 따로 쓰는 프로필로 띄운다 — 아니면 대상 아님
  if (a.some((x) => x.startsWith("obsidian://"))) return; // 링크 넘김(두 번째 실행)은 새 주인이 되지 않는다
  if (process.env.BRAIN_OBS_NOUSER === "1") return;
  let r;
  try {
    r = JSON.parse(execFileSync("py", ["-3", OBS_PIPE, "--json"], { encoding: "utf8", windowsHide: true, timeout: 15000 }));
  } catch {
    return;
  }
  if (r.state === "none")
    throw new Error(
      "격리 옵시디언을 띄우지 않음: 옵시디언 링크 파이프 주인이 없다(사용자 옵시디언 꺼짐) — 지금 띄우면 시험 창이 쥐어 뒤에 켠 사용자 옵시디언에 링크가 안 간다. " +
        "사용자 옵시디언을 먼저 켜거나 BRAIN_OBS_NOUSER=1 (py -3 3_시스템/obs_pipe.py 로 확인)",
    );
  if (r.state === "owner" && r.user === false) console.warn(`[quietwin] 링크 파이프를 이미 격리 옵시디언 pid ${r.pid} 가 쥐고 있음 — 사용자 옵시디언 링크가 안 감 (py -3 3_시스템/obs_pipe.py)`);
}

export function spawnQuiet(exe, args = [], opts = {}) {
  if (process.platform === "win32") obsGuard(exe, args);
  if (process.platform !== "win32" || process.env.BRAIN_SHOW_WINDOW === "1") return spawn(exe, args, opts);
  const extra = CHROMIUM.test(path.basename(exe)) ? ["--disable-gpu-vsync"] : [];
  return spawn("py", ["-3", HELPER, "run", "--parent", String(process.pid), "--", exe, ...extra, ...args], { ...opts, windowsHide: true });
}
