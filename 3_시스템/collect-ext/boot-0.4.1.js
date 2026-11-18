// 워커 진입 파일 — 본 코드는 sw.js(실행기) · adapters/*.js(플랫폼 어댑터). 크롬은 워커 파일 이름이 바뀌어야 재시작 때 새 코드를 읽는다(같은 이름이면 판 번호를 올려도 옛 코드 · 11-05 실측).
// sw.js·어댑터를 고치면: manifest 의 version 을 올리고 이 파일 이름을 그 판으로 바꾼다. 그러면 다음 크롬 재시작에 사람 손 없이 올라간다.
// 옛 파일은 크롬이 새 판으로 올라온 뒤에 지운다(요약 JSON 의 version 으로 확인 · 그 전에 지우면 옛 워커가 깰 때 안 잰 길을 탄다).
// 새 플랫폼 어댑터 = adapters/<이름>.js 를 아래 줄에 더한다(어댑터는 sw.js 보다 먼저 — sw.js 가 ADAPTERS 를 읽는다).
importScripts("adapters/canvas.js", "adapters/learningx.js", "sw.js");
