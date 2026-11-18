// LearningX 게시판 받기 대본(여러 과목 한 번에 · 페이지 MAIN 세계 · adapters/learningx.js 가 넣는다 · 11-16 S5 · 옛 lms/capture-board.js).
// LIST = [{course, run, prefix(원시 파일 머리), part, known:["제목|등록일시"], skip, maxPosts, tool(게시판 LTI 도구 번호 = 조리법 ext.tools.learningx)}] — 과목마다 숨은 창(iframe)에 게시판 도구를 띄워 차례로 수집.
// 받기만: 게시판·글 화면 이동과 첨부 «다운로드» 아이콘(첫 번째 i)만 누른다. 미리보기·북마크·링크복사·댓글은 누르지 않는다.
// 원본 무가공: 본문 = .ProseMirror 의 보이는 글자(text)와 원문(html) · 작성자·날짜·조회수 = 화면 라벨·값 그대로.
// 실측 교훈(10-25): ①도구가 45초까지만 기다림 → 백그라운드 + window.__collect 상태 ②history.back() 은 바깥 페이지까지 감 → 화면 버튼
// ③<script>·<style> 글자를 게시판으로 착각 → 보이는 요소만 ④버튼은 아이콘이 붙어 자신의 글자로 찾기 ⑤영어 강좌는 영어 화면
// ⑥과목마다 붙여 넣으면 사용량이 커서 한 번에 여러 과목.
// 11-05: 받은 뒤 수정된 글을 다시 연다 — 목록 화면엔 수정 시각이 없어 글 목록 API(GET · Bearer xn_api_token)로 본다. at = {글 번호: 받은 시각(ms)}. 안 되면 수정 확인만 빠진다.
// xnProbe = LearningX 모듈 목록을 원시 JSON 에 담기(대체 강의 마감 재료 · 필요한 과목만 · 실패해도 그 탐침만 빠진다).
window.__collect = { kind: "board", state: "running", log: [], results: {} };
(async (LIST) => {
const L = window.__collect;
// 확장이 돌릴 때는 window.__collectSleep(서비스 워커가 깨움) — 숨은 탭 타이머가 1분 단위로 늘어져도 대기가 제 시간에 끝난다(10-27)
const sleep = (ms) => { const w = window.__collectSleep; return w ? w(ms) : new Promise((r) => setTimeout(r, ms)); };
// 기다린 뒤 한 번 더 보고 나서 시간 초과를 판정한다(대기가 늘어지면 첫 확인만 하고 포기하던 버그)
const until = async (fn, ms = 15000) => { const t0 = Date.now(); for (;;) { try { const v = fn(); if (v) return v; } catch (e) {} if (Date.now() - t0 >= ms) return null; await sleep(200); } };
const xnToken = () => (document.cookie.match(/(?:^|;\s*)xn_api_token=([^;]+)/) || [])[1];
const xnGet = async (path) => {
  const t = xnToken();
  if (!t) return { status: "no_token" };
  try {
    const r = await fetch(path, { credentials: "include", headers: { Accept: "application/json", Authorization: "Bearer " + t } });
    const text = await r.text();
    let body = null;
    try { body = JSON.parse(text.replace(/^while\(1\);/, "")); } catch (e) {}
    return { status: r.status, body };
  } catch (e) { return { status: "net" }; }
};
// 글 목록 전부(쪽마다 GET 하나) — {items, whole}. 쪽 끝을 모르는 모양이어도 빈 쪽·같은 쪽이 오면 멈춘다.
async function listPosts(course, bid) {
  const items = [], seen = new Set();
  for (let page = 1; page <= 30; page++) {
    const r = await xnGet(`/learningx/api/v1/learningx_board/courses/${course}/boards/${bid}/posts?page=${page}`);
    if (r.status !== 200 || !r.body || !Array.isArray(r.body.items)) return { items, whole: false, status: r.status };
    const fresh = r.body.items.filter((x) => x && x.id && !seen.has(x.id));
    if (!fresh.length) break;
    for (const x of fresh) { seen.add(x.id); items.push({ id: x.id, title: x.title, created_at: x.created_at, post_updated_at: x.post_updated_at }); }
    const pg = r.body.pagination || {};
    if (pg.next_page === null || pg.has_next === false || (pg.total_pages && page >= pg.total_pages) || (pg.total_count && items.length >= pg.total_count)) break;
  }
  return { items, whole: true };
}
const kstMinute = (s) => { const ms = Date.parse(s); return Number.isNaN(ms) ? null : new Date(ms + 9 * 3600000).toISOString().slice(0, 16).replace("T", " "); };
async function runBoard(CFG, root) {
  const fr = () => root.querySelector("iframe#tool_content, iframe[name=tool_content]");
  const ready = await until(() => fr() && fr().contentWindow.location.pathname.includes("learningx_board") && fr().contentWindow.document.body.innerText.length > 10, 30000);
  if (!ready) {  // 어디서 멈췄는지 남긴다(10-26 실수집 8과목 실패 — 원인 가르기용)
    let at = null, text = null;
    try { at = fr() ? fr().contentWindow.location.href : "iframe 없음"; text = fr() ? fr().contentWindow.document.body.innerText.slice(0, 200) : null; } catch (e) { at = "읽기 실패: " + e.message; }
    return { error: "no_board_tool", root: root.location ? root.location.href : null, at, text };
  }
  const w = fr().contentWindow;
  const d = () => w.document;
  const fire = (el) => ["mousedown", "mouseup", "click"].forEach((t) => el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: w })));
  const leaves = () => [...d().body.querySelectorAll("*")].filter((e) => e.children.length === 0 && !/^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|TITLE)$/.test(e.tagName) && e.getClientRects().length && e.textContent.trim());
  const leaf = (t) => leaves().find((e) => e.textContent.trim() === t);
  const own = (e) => [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.nodeValue).join("").trim();
  const byText = (...ts) => [...d().body.querySelectorAll("*")].find((e) => ts.includes(own(e)) && e.getClientRects().length);
  const skip = new RegExp(CFG.skip || "Q&A|QnA|질문|자유|토론|팀", "i");
  const known = new Set(CFG.known || []);
  const atList = () => /\/boards$/.test(w.location.pathname);
  const atBoard = () => /\/boards\/\d+$/.test(w.location.pathname) && d().querySelectorAll("tr").length > 1;
  const atPost = () => /\/posts\/\d+/.test(w.location.pathname) && /조회수|View/.test(d().body.innerText);
  const toListBtn = () => byText("목록", "목록으로 돌아가기", "Go to list");
  const toAllBtn = () => byText("전체 게시판 목록 바로가기", "Show all board list");
  const toList = async () => {
    for (let i = 0; i < 3 && !atList(); i++) {
      if (atPost()) { const b = toListBtn(); if (b) fire(b); await until(atBoard, 8000); }
      if (atBoard()) { const b = toAllBtn(); if (b) fire(b); await until(atList, 8000); }
    }
    return atList();
  };
  if (!(await toList())) return { error: "board_list" };
  await until(() => /게시판|boards/i.test(d().body.innerText));
  const NOT = /^(\d+|최근|전체 게시판|비밀글 허용|게시판|All boards|Secret post|Updated)$|^\d{4}-\d{2}-\d{2}/;
  const boardNames = [...new Set(leaves().map((e) => e.textContent.trim()).filter((t) => !NOT.test(t)))];
  const out = { kind: "board", run: CFG.run, part: CFG.part || 1, course: CFG.course, capturedAt: new Date().toISOString(), boards: [] };
  let opened = 0, more = false;
  const metaOf = () => {
    const m = {};
    for (const e of leaves()) {
      const lab = e.textContent.trim().replace(/\s*:\s*$/, "");
      if (/^(작성자|등록일시|수정일시|조회수|Name|Created Date|Modified Date|Updated Date|View|Views)$/.test(lab) && e.parentElement) m[lab] = e.parentElement.innerText.replace(e.textContent, "").trim();
    }
    return m;
  };
  for (const name of boardNames) {
    const b = { name, skipped: skip.test(name), posts: [], seen: 0 };
    out.boards.push(b);
    if (b.skipped || more) continue;
    if (!(await toList())) { b.error = "back_to_list"; continue; }
    const bl = await until(() => leaf(name));
    if (!bl) { b.error = "no_board_link"; continue; }
    fire(bl);
    if (!(await until(atBoard))) { b.error = "board_open"; continue; }
    b.path = w.location.pathname;
    L.log.push(`${CFG.course} 게시판 ${name}`);
    // 받은 뒤 수정된 글 = 목록 API 의 내용 수정 시각이 받은 시각보다 늦은 글(첫 받기·토큰 없음 = 빈 집합 → 전처럼 돈다)
    const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();
    const revisit = new Set(), updated = {};    // 열쇠 = 제목|등록 시각(분) · 같은 제목이 없으면 제목만으로도 — 시각 꼴이 어긋나도 찾게
    const bid = (b.path.match(/\/boards\/(\d+)/) || [])[1];
    if (bid) {
      const lp = await listPosts(CFG.course, bid);
      b.live = lp.items;
      b.live_whole = lp.whole;
      if (lp.status !== undefined) b.live_status = lp.status;
      const count = {};
      for (const it of lp.items) count[norm(it.title)] = (count[norm(it.title)] || 0) + 1;
      for (const it of lp.items) {
        const keys = [`${norm(it.title)}|${kstMinute(it.created_at)}`, ...(count[norm(it.title)] === 1 ? [norm(it.title)] : [])];
        const got = (CFG.at || {})[String(it.id)], up = Date.parse(it.post_updated_at);
        for (const k of keys) {
          updated[k] = it.post_updated_at;
          if (got && !Number.isNaN(up) && up > got) revisit.add(k);
        }
      }
    }
    for (let page = 1; page < 40; page++) {
      const head = [...d().querySelectorAll("tr")][0];
      const cols = [...head.querySelectorAll("th,td")].map((x) => x.innerText.trim());
      const ci = (k) => cols.findIndex((c) => k.split("|").includes(c));
      const TITLE = "제목|Title", DATE = "등록일시|Created Date";
      const rows = [...d().querySelectorAll("tr")].slice(1).map((tr) => [...tr.querySelectorAll("td")].map((td) => td.innerText.trim()));
      for (const r of rows) {
        const title = r[ci(TITLE)], date = r[ci(DATE)];
        if (!title) continue;
        b.seen++;
        const key = `${title}|${date}`;
        const rk = [`${norm(title)}|${date}`, norm(title)].find((k) => revisit.has(k));
        if (known.has(key) && !rk) continue;
        if (opened >= (CFG.maxPosts || 60)) { more = true; break; }
        const cell = [...d().querySelectorAll("tr")].slice(1).map((tr) => tr.querySelectorAll("td")[ci(TITLE)]).find((td) => td && td.innerText.trim() === title);
        if (!cell) { b.posts.push({ key, error: "no_row" }); continue; }
        fire([...cell.querySelectorAll("*")].reverse().find((e) => e.textContent.trim() === title) || cell);
        if (!(await until(atPost))) { b.posts.push({ key, error: "post_open" }); continue; }
        await sleep(300);
        const pm = d().querySelector(".ProseMirror");
        const labelAtt = leaf("첨부파일") || leaf("Attachments");
        const attEls = labelAtt ? [...labelAtt.parentElement.querySelectorAll("span")].filter((s) => s.nextElementSibling && s.nextElementSibling.tagName === "I") : [];
        const post = {
          key, title, list_date: date, list_row: r, path: w.location.pathname, meta: metaOf(), rev: known.has(key) || undefined, post_updated_at: updated[`${norm(title)}|${date}`] || updated[norm(title)],
          text: pm ? pm.innerText : "", html: pm ? pm.innerHTML : "",
          links: pm ? [...pm.querySelectorAll("a[href]")].map((a) => ({ text: a.textContent, href: a.getAttribute("href") })) : [],
          attachments: attEls.map((s) => s.textContent.trim()),
        };
        for (const s of attEls) { fire(s.parentElement.querySelectorAll("i")[0]); await sleep(2200); }
        b.posts.push(post);
        known.add(key);
        revisit.delete(`${norm(title)}|${date}`);
        revisit.delete(norm(title));
        opened++;
        L.log.push(`${CFG.course} 글 ${opened}: 첨부 ${post.attachments.length}`);
        const back = toListBtn();
        if (back) fire(back);
        if (!(await until(atBoard))) { b.error = "back_to_board"; break; }
        await sleep(300);
      }
      if (more || b.error) break;
      const table = d().querySelector("table");
      const bottom = table ? table.getBoundingClientRect().bottom : 0;
      const nxt = leaves().find((e) => e.textContent.trim() === String(page + 1) && e.getBoundingClientRect().top > bottom);
      if (!nxt) break;
      fire(nxt);
      await sleep(1500);
    }
  }
  await toList();
  if (CFG.xnProbe) {                     // 이 대본이 도는 때는 게시판 도구를 띄운 뒤라 토큰이 있다 · 내 번호·로그인 이름은 LearningX 주소가 요구한다
    let me = null;
    try { me = JSON.parse((await (await fetch("/api/v1/users/self/profile", { credentials: "include", headers: { Accept: "application/json" } })).text()).replace(/^while\(1\);/, "")); } catch (e) {}
    out.xn = { modules: await xnGet(`/learningx/api/v1/courses/${CFG.course}/modules?include_detail=true`) };
    if (me && me.id) out.xn.components = await xnGet(`/learningx/api/v1/courses/${CFG.course}/allcomponents_db?user_id=${me.id}&user_login=${encodeURIComponent(me.login_id || "")}&role=1`);
    L.log.push(`${CFG.course} LearningX 탐침 ${out.xn.modules.status}/${(out.xn.components || {}).status}`);
  }
  const blob = new Blob([JSON.stringify(out)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${CFG.prefix || ""}board-${CFG.course}-${CFG.run}-${out.part}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  return { more, opened, boards: out.boards.filter((x) => x.seen || x.skipped || x.posts.length).map((x) => ({ name: x.name, skipped: x.skipped, seen: x.seen, new: x.posts.length, att: x.posts.reduce((s, p) => s + (p.attachments || []).length, 0), err: x.error || x.posts.filter((p) => p.error).length || 0 })) };
}
for (const CFG of LIST) {
  try {
    const f = document.createElement("iframe");
    f.style.cssText = "position:fixed;left:0;top:0;width:1280px;height:900px;opacity:0.01;z-index:-1;border:0";
    const tool = CFG.tool;
    if (!/^\d+$/.test(String(tool))) throw new Error("게시판 도구 번호 없음(조리법 ext.tools.learningx)");
    f.src = `/courses/${CFG.course}/external_tools/${tool}`;
    document.body.appendChild(f);
    // 붙이자마자의 contentDocument 는 빈 about:blank(이미 complete) — 그걸 넘기면 진짜 과목 페이지가 뜬 뒤에도 옛 문서를 뒤진다
    // (10-27 실수집 3회 8과목 «iframe 없음»). 과목 도구 주소로 바뀐 문서가 다 뜰 때까지 기다린다.
    await until(() => { const d = f.contentDocument; return d && d.location && d.location.pathname.includes("/external_tools/") && d.readyState === "complete"; }, 30000);
    L.results[CFG.course] = await runBoard(CFG, f.contentDocument);
    f.remove();
  } catch (e) {
    L.results[CFG.course] = { error: String(e.message || e) };
  }
  await sleep(1500);
}
L.state = "done";
})(__LIST__);
"started";
