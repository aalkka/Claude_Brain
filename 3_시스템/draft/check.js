// 초안 원칙 검사 — 비교 한 장의 칸(frame)마다 돈다. 결과를 부모(비교.html)에 알린다.
// 근거 = [[외부뇌-디자인원칙]] D1·D2·D6·D8. 자료(노트 이름·값)는 data-d 를 단 요소에 넣어 검사에서 뺀다.
(() => {
  const ID = window.__frame || "?";
  const vis = (el) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
  };
  const run = () => {
    const out = { 문장: [], 묻는말: [], 크기: [], 색: [], 이름: [], 단추: [], 넘침: [], 글자: 0, 색칠: 0 };
    // D1 첫 화면 글 · D6 글자 크기
    const sizes = new Set();
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n; (n = tw.nextNode()); ) {
      const t = n.textContent.replace(/\s+/g, " ").trim();
      const el = n.parentElement;
      if (!t || !el || el.closest("script,style") || !vis(el)) continue;
      sizes.add(Math.round(parseFloat(getComputedStyle(el).fontSize) * 2) / 2);
      if (el.closest("[data-d]")) continue;
      // D9 묻는 말(data-ask) = 문장 허용 · 대신 격식체(«…습니까?»)
      if (el.closest("[data-ask]")) { if (!/(습니까|니까)\?$/.test(t)) out.묻는말.push(t.slice(0, 40)); continue; }
      out.글자 += [...t.replace(/[\d\s.,:;·/%()+\-−×~✦…→←↑↓?!]/g, "")].length;
      const spaces = (t.match(/ /g) || []).length;
      if (t.length >= 10 && (spaces >= 3 || /(다|요|까|음|함)[.!?]?$/.test(t) || /[.!?] \S/.test(t))) out.문장.push(t.slice(0, 40));
    }
    out.크기 = [...sizes].sort((a, b) => a - b);
    // D6 하드코딩 색 — 이 안의 <style data-own> 과 style 속성
    const own = [...document.querySelectorAll("style[data-own]")].map((s) => s.textContent).join("\n")
      + "\n" + [...document.querySelectorAll("[style]")].map((e) => e.getAttribute("style")).join("\n");
    const bare = own.replace(/\/\*[\s\S]*?\*\//g, "").replace(/var\([^()]*(\([^()]*\))?[^()]*\)/g, "");
    out.색 = (bare.match(/#[0-9a-fA-F]{3,8}\b|\b(rgba?|hsla?)\([^)]*\)|\b(white|black|red|blue|green|gray|grey|orange|yellow|purple)\b(?=\s*[;}"])/g) || []).slice(0, 6);
    // D2 마우스 이름 = 낱말만(≤ 8자 · — ( 없음) · 글자 단추 ≤ 6자
    for (const el of document.querySelectorAll("[aria-label],[title]")) {
      const t = (el.getAttribute("aria-label") || el.getAttribute("title") || "").trim();
      if ([...t].length > 8 || /[—(]/.test(t)) out.이름.push(t.slice(0, 30));
    }
    for (const el of document.querySelectorAll("button,[role=button],.btn,.chip")) {
      if (!vis(el) || el.closest("[data-d]")) continue;
      const t = (el.innerText || "").trim();
      if ([...t].length > 6) out.단추.push(t.slice(0, 20));
    }
    // D8 넘침 — 글자가 칸 밖으로(말줄임은 허용) · 가로 스크롤
    for (const el of document.querySelectorAll("body *")) {
      if (!vis(el) || ![...el.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())) continue;
      const s = getComputedStyle(el);
      if (s.overflowX === "visible" && s.display !== "inline" && el.scrollWidth > el.clientWidth + 1) out.넘침.push((el.innerText || "").trim().slice(0, 20));
    }
    if (document.documentElement.scrollWidth > innerWidth + 1) out.넘침.push("가로 스크롤");
    // D5 색은 상태에만 — 색 쓴 요소 수(판정 없이 셈)
    const probe = (v) => { const p = document.createElement("i"); p.style.color = `var(${v})`; document.body.appendChild(p); const c = getComputedStyle(p).color; p.remove(); return c; };
    const hues = new Set(["--text-accent", "--interactive-accent", "--text-error", "--text-warning", "--text-success"].map(probe));
    for (const el of document.querySelectorAll("body *")) {
      const own = el.matches("svg") || [...el.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim());
      if (own && !el.closest("svg *") && vis(el) && hues.has(getComputedStyle(el).color)) out.색칠++;
    }
    parent.postMessage({ t: "draft-frame", id: ID, h: Math.ceil(document.documentElement.getBoundingClientRect().height), r: out }, "*");
  };
  addEventListener("message", (e) => {
    if (e.data && e.data.t === "draft-theme") { document.documentElement.dataset.theme = e.data.v; }
  });
  if (document.readyState === "complete") setTimeout(run, 50); else addEventListener("load", () => setTimeout(run, 50));
})();
