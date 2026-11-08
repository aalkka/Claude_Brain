// 크롬을 디버깅 파이프로 띄워 압축 푼 확장을 넣는다(브랜드 크롬은 137 부터 --load-extension 을 막는다 — 11-03 실측 156).
//   node chrome_pipe.mjs <chrome.exe> <확장 폴더> [크롬 인자…]
// 크롬이 끝날 때까지 산다. 이 프로세스를 죽이면 파이프가 닫혀 크롬도 끝난다.
import { spawn } from "node:child_process";

const [, , exe, ext, ...rest] = process.argv;
const pr = spawn(exe, ["--remote-debugging-pipe", "--enable-unsafe-extension-debugging", ...rest], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
const toChrome = pr.stdio[3], fromChrome = pr.stdio[4];
let buf = "";
fromChrome.on("data", (d) => {
  buf += d.toString("utf8");
  for (let i; (i = buf.indexOf("\0")) >= 0; buf = buf.slice(i + 1)) {
    const m = JSON.parse(buf.slice(0, i));
    if (m.id === 1) console.log(m.error ? "확장 넣기 실패 " + JSON.stringify(m.error) : "확장 넣음 " + m.result.id);
  }
});
toChrome.write(JSON.stringify({ id: 1, method: "Extensions.loadUnpacked", params: { path: ext } }) + "\0");
process.stdin.on("data", (d) => {
  const t = String(d);
  if (t.includes("close")) toChrome.write(JSON.stringify({ id: 2, method: "Browser.close" }) + "\0");  // 시험이 크롬을 정상 종료할 때(쿠키 기록·exit_type 까지 사람이 닫는 것과 같은 길)
  const m = t.match(/^open (\S+)/m);
  if (m) toChrome.write(JSON.stringify({ id: 3, method: "Target.createTarget", params: { url: m[1] } }) + "\0");  // 사람이 주소를 연 셈(재로그인 시험) — 창 없는 크롬 안의 탭이라 앞 창을 안 뺏는다
});
pr.on("exit", (c) => process.exit(c ?? 0));
for (const s of ["SIGINT", "SIGTERM"]) process.on(s, () => pr.kill());
