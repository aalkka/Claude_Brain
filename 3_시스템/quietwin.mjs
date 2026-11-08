// 시험이 창을 띄울 때 쓰는 공통 부품(ADR-044). child_process.spawn 과 같은 꼴이고 창만 사용자 화면 밖에 뜬다.
//   import { spawnQuiet } from "file:///C:/Claude_Brain/3_시스템/quietwin.mjs";
// BRAIN_SHOW_WINDOW=1 = 사람이 보려고 일부러 띄울 때만.
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HELPER = path.join(path.dirname(fileURLToPath(import.meta.url)), "quietwin.py");
// 화면 밖 데스크톱엔 수직 동기 신호가 없어 그리기가 초당 13번으로 떨어진다(11-05 실측 · 이 인자로 150).
const CHROMIUM = /obsidian|chrome|msedge|electron/i;

export function spawnQuiet(exe, args = [], opts = {}) {
  if (process.platform !== "win32" || process.env.BRAIN_SHOW_WINDOW === "1") return spawn(exe, args, opts);
  const extra = CHROMIUM.test(path.basename(exe)) ? ["--disable-gpu-vsync"] : [];
  return spawn("py", ["-3", HELPER, "run", "--parent", String(process.pid), "--", exe, ...extra, ...args], { ...opts, windowsHide: true });
}
