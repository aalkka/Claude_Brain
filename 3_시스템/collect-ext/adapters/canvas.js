// Canvas 플랫폼 어댑터(워커 쪽 · 11-16 S5 · 옛 sw.js 0.3.1 의 Canvas 부분). Canvas 를 쓰는 사이트 어디든 — 사이트 값(호스트·과목 번호)은 조리법·known 에만.
// 단위 = 강좌 번호. 지문 칸: a 공지 · p 할 일(과제·퀴즈·제출 상태) · m 모듈(무거움). 받기 = canvas-page.js(수집 탭 MAIN 세계) → 원시 <raw_prefix>canvas-<run>.json + 첨부.
(self.ADAPTERS = self.ADAPTERS || {}).canvas = {
  slot: "canvas",                               // 요약 칸 이름(PC 어댑터 collect-adapters/canvas.py 가 읽는다)
  label: "Canvas",
  loginProbe: "/api/v1/users/self",             // 로그인 판정 — 비로그인 = 404(10-25 실측) · 401 · 돌림
  sessionCookie: "_normandy_session",           // Canvas 세션 쿠키(11-03 실측) — 끊겼을 때 이것이 남아 있으면 서버 쪽 세션이 끝난 것이다

  // 학기로 고정한 창 — 날마다 미는 창은 지난 글이 빠질 때마다 «바뀜»으로 보인다(2~7월 · 8~2월 학기)
  termWindow() {
    const d = new Date(), y = d.getFullYear(), m = d.getMonth() + 1;
    const [a, b] = m >= 8 ? [`${y}-08-01`, `${y + 1}-02-28`] : m >= 2 ? [`${y}-02-01`, `${y}-07-31`] : [`${y - 1}-08-01`, `${y}-02-28`];
    return { from: a, to: b };
  },

  // 공지·할 일은 전 강좌가 요청 하나씩이다
  async signals(x, units, out) {
    const { from, to } = this.termWindow();
    const ctx = units.map((c) => `context_codes[]=course_${c}`).join("&");
    const ann = await x.getJson(`/api/v1/announcements?${ctx}&start_date=${from}&end_date=${to}&per_page=100`, false, "ann");
    if (Array.isArray(ann)) {
      const by = {};
      for (const it of ann) {
        const c = String(it.context_code || "").replace("course_", "");
        (by[c] = by[c] || []).push(x.hash(`${it.id}|${it.title}|${it.posted_at}|${it.message}|${(it.attachments || []).map((f) => f.id).join()}`));
      }
      for (const c of units) out[c].a = x.hashOf(by[c] || []);
    }
    const plan = await x.getJson(`/api/v1/planner/items?start_date=${from}&end_date=${to}&per_page=100`, false, "plan");
    if (Array.isArray(plan)) {
      const by = {};
      for (const it of plan) {
        const p = it.plannable || {}, s = it.submissions || {};
        (by[it.course_id] = by[it.course_id] || []).push(x.hash(`${it.plannable_type}|${it.plannable_id}|${p.title}|${p.due_at || p.todo_date}|${p.updated_at}|${s.submitted}|${s.graded}`));
      }
      for (const c of units) out[c].p = x.hashOf(by[c] || []);
    }
  },

  // 모듈 목록은 강좌마다 요청이 들어 무거운 신호
  async heavy(x, units, out, cache) {
    for (const c of units) {
      const mods = await x.getJson(`/api/v1/courses/${c}/modules?per_page=100`, false, "mod");
      if (Array.isArray(mods)) out[c].m = x.hashOf(mods.map((m) => `${m.id}|${m.name}|${m.items_count}`));
    }
    return cache;
  },

  async collect(x, tabId, job) {
    await x.inMain(tabId, (cfg) => { window.__CFG__ = cfg; }, [{ courses: job.units.map(Number), run: x.run, knownFiles: x.known.knownFiles || [], prefix: x.raw_prefix }]);
    await x.fileInMain(tabId, "adapters/canvas-page.js");
    return x.poll(tabId, "canvas", 15 * 60 * 1000);
  },

  async probe(x, unit, out) {
    await x.probeOne(out, "files_listing", `/api/v1/courses/${unit}/files?sort=updated_at&order=desc&per_page=1`);
    await x.probeOne(out, "stream_summary", "/api/v1/users/self/activity_stream/summary");
    await x.probeOne(out, "active_courses", "/api/v1/courses?enrollment_state=active&per_page=100");
  },

  // 새 학기에 과목 지도가 낡는 것을 잡는다 — 조용히 안 받는 일이 없게(받기가 실패해도 본다)
  async after(x, job, summary) {
    if (job.why !== "daily" && job.why !== "button") return;
    const act = await x.getJson("/api/v1/courses?enrollment_state=active&per_page=100").catch(() => null);
    if (Array.isArray(act)) summary.activeCourses = act.map((c) => ({ id: c.id, name: c.name }));
  },
};
