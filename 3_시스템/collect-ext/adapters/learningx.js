// LearningX 게시판 어댑터(워커 쪽 · 11-16 S5 · 옛 sw.js 0.3.1 의 게시판 부분). Canvas 안에 LTI 로 붙는 LearningX 게시판 — 사이트 값은 조리법·known 에만.
// 단위 = 강좌 번호. 지문 칸: b 게시판(무거움 · 글 목록 1쪽). 받기 = learningx-page.js(수집 탭 MAIN 세계) → 원시 <raw_prefix>board-<강좌>-<run>-<쪽>.json.
(self.ADAPTERS = self.ADAPTERS || {}).learningx = {
  slot: "board",                                // 요약 칸 이름(PC 어댑터 collect-adapters/learningx.py 가 읽는다)
  label: "게시판",
  cover: "board",                               // 이 신호가 200 이면 새 글을 신호로 잡으니 전 단위 안전망을 길게(FULL_EVERY_SIGNAL)
  allowNonGet: ["/learningx/lti/"],             // 게시판 도구 진입(LTI) — 0.1.3 관찰 수집(11-03)에서 GET 아닌 것은 이것과 조회수 올리기(view_count · 막힘)뿐
  tokenCookie: "xn_api_token",                  // 게시판 API 는 쿠키만으론 401 · Bearer 이 토큰이면 200(11-03 탐침). 토큰은 게시판 도구를 띄울 때 생기는 세션 쿠키
  skip: /Q&A|QnA|질문|자유|토론|팀/i,            // learningx-page.js 와 같은 제외(학생 게시판)
  postKeys: ["id", "title", "attachment_count", "created_at", "post_updated_at"],   // 글이 바뀌었는지 보는 칸(11-04 실측) — 조회수·댓글 수·updated_at 은 뺀다(내용 수정은 post_updated_at)

  // 게시판 지문 — 탭을 열지 않는다. 토큰이 없으면(크롬을 다시 켠 뒤 첫 전 단위 받기 전) 이 신호만 빠진다. 게시판 번호는 cache 에 두고 글 목록 1쪽만 본다.
  async heavy(x, units, out, cache) {
    const c0 = await x.cookie(this.tokenCookie);
    if (!c0) { x.sig.board = "no_token"; return cache; }
    const next = { ...cache };
    for (const c of units) {
      const base = `/learningx/api/v1/learningx_board/courses/${c}/boards`;
      if (!next[c]) {
        const list = await x.getAuth(base, c0.value, "board");
        if (!Array.isArray(list)) continue;
        next[c] = list.filter((b) => b && b.id && !this.skip.test(b.title || "")).map((b) => b.id);
      }
      const prints = [];
      let whole = true;
      for (const id of next[c]) {
        const p = await x.getAuth(`${base}/${id}/posts?page=1`, c0.value, "board");
        if (!p || !Array.isArray(p.items)) { whole = false; break; }
        for (const it of p.items) prints.push(x.hash(JSON.stringify(this.postKeys.map((k) => it[k]))));
      }
      if (whole) out[c].b = x.hashOf(prints);
    }
    return next;
  },

  // at = 글 번호 → 받은 시각(받은 뒤 수정된 글을 다시 연다) · xnProbe = LearningX 모듈 목록을 잴 강좌 — 둘 다 PC 의 learningx 어댑터가 정한다
  async collect(x, tabId, job) {
    const k = x.known;
    const tool = (x.tools || {}).learningx;       // 게시판 LTI 도구 번호 — 학교마다 다르다(조리법 ext.tools.learningx · S7)
    const list = job.units.map(Number).map((c) => ({ course: c, run: x.run, prefix: x.raw_prefix, tool, known: (k.board || {})[String(c)] || [], at: (k.boardAt || {})[String(c)] || {}, xnProbe: (k.xnProbe || []).includes(c) }));
    await x.inMain(tabId, (l) => { window.__LIST__ = l; }, [list]);
    await x.fileInMain(tabId, "adapters/learningx-page.js");
    return x.poll(tabId, "board", 40 * 60 * 1000);
  },

  // 게시판 과목 하나의 오류 = 부분 오류(대기열·알림으로만 · 전 단위 받기를 되풀이하지 않게)
  softBad(slot) {
    return Object.values((slot || {}).results || {}).some((r) => r && r.error);
  },

  // 게시판 API 를 탭 밖에서 부를 수 있는지 — 내용은 남기지 않고 상태·개수·칸 이름만
  async probe(x, unit, out) {
    const base = `/learningx/api/v1/learningx_board/courses/${unit}/boards`;
    const token = await x.cookie(this.tokenCookie);
    const auth = token ? { Authorization: "Bearer " + token.value } : null;
    out.xn_api_token = !!token;
    let boards = await x.probeOne(out, "boards_cookie", base);
    if (auth) boards = (await x.probeOne(out, "boards_bearer", base, auth)) || boards;
    const list = Array.isArray(boards) ? boards : (boards && (boards.boards || boards.data || boards.items)) || [];
    const b = list.find((it) => it && it.id && !this.skip.test(it.title || "")) || list.find((it) => it && it.id);
    if (b && auth) await x.probeOne(out, "posts_bearer", `${base}/${b.id}/posts?page=1`, auth);
  },
};
