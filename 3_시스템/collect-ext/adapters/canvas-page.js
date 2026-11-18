// Canvas 받기 대본(페이지 MAIN 세계 · adapters/canvas.js 가 넣는다 · 11-16 S5 · 옛 lms/capture-canvas.js). 받기만: GET + 다운로드.
// CFG = {courses, run, knownFiles, prefix(원시 파일 머리 = 조리법 raw_prefix)}.
// 첫 줄의 CFG 를 바꿔 붙인다: {courses:[강좌번호], run:"YYYYMMDD-HHMM", knownFiles:[파일번호]}
// 원본 무가공: API 응답 필드를 그대로 담고, HTML 은 원문(html)과 보이는 글자(text)를 함께 담는다.
// 내용은 JSON 파일로 바로 내려받고(브라우저 → 디스크), 호출한 쪽에는 개수만 돌려준다.
// 브라우저 도구가 45초까지만 기다리므로 백그라운드로 돌리고 window.__collect 로 상태를 본다.
window.__collect = { kind: "canvas", state: "running", result: null };
(async (CFG) => {
const sleep = (ms) => { const w = window.__collectSleep; return w ? w(ms) : new Promise((r) => setTimeout(r, ms)); };  // capture-board.js 와 같은 이유
let denied = [];
async function getAll(path) {
  const out = [];
  let url = path;
  for (let i = 0; url && i < 50; i++) {
    const r = await fetch(url, { credentials: "include", headers: { Accept: "application/json" } });
    if (r.status === 401) {     // 로그인 상태에서도 권한 없는 길은 401 — 끊김은 users/self 로만 판정한다. 한 과목이 전 수집을 세우지 않게(11-03 검토)
      if ((await fetch("/api/v1/users/self", { credentials: "include" })).status === 401) throw new Error("login_required");
      denied.push(path.split("?")[0]);
      return { status: 401, items: out };
    }
    if (r.status === 429) throw new Error("api_429");   // 학교 서버가 그만하라는 뜻 — 이번 받기를 멈춘다(확장이 뒤로 물린다)
    if (r.status !== 200) return { status: r.status, items: out };
    const j = JSON.parse((await r.text()).replace(/^while\(1\);/, ""));
    if (!Array.isArray(j)) return { status: 200, items: j };
    out.push(...j);
    const m = /<([^>]+)>;\s*rel="next"/.exec(r.headers.get("Link") || "");
    url = m ? m[1] : null;
  }
  return { status: 200, items: out };
}
// HTML → 보이는 글자. DOMParser 문서는 그림·스크립트를 불러오지 않는다(무해). 줄바꿈만 블록·br 에서 넣는다.
function textOf(html) {
  const doc = new DOMParser().parseFromString(html || "", "text/html");
  const BLOCK = /^(P|DIV|LI|UL|OL|H[1-6]|TR|TABLE|BLOCKQUOTE|PRE|SECTION|ARTICLE|HEADER|FOOTER)$/;
  let s = "";
  const walk = (n) => {
    if (n.nodeType === 3) { s += n.nodeValue; return; }
    if (n.nodeType !== 1) return;
    if (n.tagName === "BR") { s += "\n"; return; }
    if (n.tagName === "SCRIPT" || n.tagName === "STYLE") return;
    const b = BLOCK.test(n.tagName);
    if (b && s && !s.endsWith("\n")) s += "\n";
    if (n.tagName === "TD" || n.tagName === "TH") s += "\t";
    n.childNodes.forEach(walk);
    if (b && !s.endsWith("\n")) s += "\n";
  };
  walk(doc.body);
  return s.replace(/\n{3,}/g, "\n\n").trim();
}
function linksOf(html) {
  const doc = new DOMParser().parseFromString(html || "", "text/html");
  return [...doc.querySelectorAll("a[href]")].map((a) => ({ text: a.textContent, href: a.getAttribute("href") }));
}
const fileMeta = async (course, id) => {
  for (const p of [`/api/v1/courses/${course}/files/${id}`, `/api/v1/files/${id}`]) {
    const r = await fetch(p, { credentials: "include", headers: { Accept: "application/json" } });
    if (r.status === 200) return JSON.parse((await r.text()).replace(/^while\(1\);/, ""));
  }
  return null;
};
const known = new Set((CFG.knownFiles || []).map(String));
const data = { kind: "canvas", run: CFG.run, capturedAt: new Date().toISOString(), host: location.host, courses: [] };
const downloads = [];
const summary = [];
try {
  for (const id of CFG.courses) {
    denied = [];
    const c = { id, files: {}, status: {} };  // status = 요청 결과 — 빈 목록이 «없음»인지 «실패»인지 가른다(지워진 과제 판정)
    const info = await getAll(`/api/v1/courses/${id}?include[]=syllabus_body`);
    c.course = info.items;
    c.syllabus = { html: (info.items || {}).syllabus_body || "", text: textOf((info.items || {}).syllabus_body) };
    const ann = await getAll(`/api/v1/courses/${id}/discussion_topics?only_announcements=true&per_page=100`);
    c.status.announcements = ann.status;
    c.announcements = (ann.items || []).map((x) => ({ ...x, _text: textOf(x.message), _links: linksOf(x.message) }));
    const asg = await getAll(`/api/v1/courses/${id}/assignments?include[]=submission&per_page=100`);
    c.status.assignments = asg.status;
    c.assignments = (asg.items || []).map((x) => ({ ...x, _text: textOf(x.description), _links: linksOf(x.description) }));
    const mods = await getAll(`/api/v1/courses/${id}/modules?include[]=items&include[]=content_details&per_page=100`);  // content_details = 항목의 기한 칸(요청 수는 그대로)
    c.status.modules = mods.status;
    c.modules = mods.items || [];
    // 파일: 모듈 파일 항목 · 공지 첨부 · 과제·공지 본문 속 /files/<번호> 링크 — 어디서 왔는지(ref)를 함께 적는다
    const addFile = (meta, ref) => {
      if (!meta || !meta.id) return;
      const k = String(meta.id);
      if (!c.files[k]) c.files[k] = { meta, refs: [] };
      c.files[k].refs.push(ref);
    };
    for (const m of c.modules) for (const it of m.items || []) {
      if (it.type === "File" && it.url) {
        const r = await fetch(it.url.replace(location.origin, ""), { credentials: "include", headers: { Accept: "application/json" } });
        if (r.status === 200) addFile(JSON.parse((await r.text()).replace(/^while\(1\);/, "")), { kind: "module", module: m.name, item: it.title, item_id: it.id });
      }
    }
    for (const a of c.announcements) for (const f of a.attachments || []) addFile(f, { kind: "announcement", id: a.id });
    // 내 제출 파일(과제의 submission.attachments) — 제출본을 원본 층 «제출»에 보관(작업 폴더 원칙 · 3_시스템/work.py · 10-31)
    for (const x of c.assignments) for (const f of (x.submission && x.submission.attachments) || []) addFile(f, { kind: "submission", id: x.id });
    for (const [kind, list, field] of [["announcement", c.announcements, "message"], ["assignment", c.assignments, "description"]]) {
      for (const x of list) {
        for (const m of (x[field] || "").matchAll(/\/files\/(\d+)/g)) {
          if (c.files[m[1]]) { c.files[m[1]].refs.push({ kind, id: x.id, link: true }); continue; }
          addFile(await fileMeta(id, m[1]), { kind, id: x.id, link: true });
        }
      }
    }
    let dl = 0;
    for (const [k, f] of Object.entries(c.files)) {
      if (known.has(k) || !f.meta.url) continue;
      downloads.push({ course: id, id: f.meta.id, display_name: f.meta.display_name, filename: f.meta.filename, size: f.meta.size });
      const a = document.createElement("a");
      a.href = f.meta.url;
      a.download = f.meta.display_name || "";
      document.body.appendChild(a);
      a.click();
      a.remove();
      dl++;
      await sleep(1800);
    }
    data.courses.push(c);
    summary.push({ id, 공지: c.announcements.length, 과제: c.assignments.length, 계획서: c.syllabus.text.length, 파일: Object.keys(c.files).length, 다운로드: dl, ...(denied.length ? { 막힘: denied } : {}) });
  }
} catch (e) {
  data.error = String(e.message || e);
}
data.downloads = downloads;
const blob = new Blob([JSON.stringify(data)], { type: "application/json" });
const a = document.createElement("a");
a.href = URL.createObjectURL(blob);
a.download = `${CFG.prefix || ""}canvas-${CFG.run}.json`;
document.body.appendChild(a);
a.click();
a.remove();
window.__collect.result = { error: data.error || null, summary, jsonBytes: blob.size };
window.__collect.state = data.error ? "error" : "done";
})(__CFG__);
"started";
