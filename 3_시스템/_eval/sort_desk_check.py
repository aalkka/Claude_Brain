"""수집 창 분류 칸(S4 · 초안 B «규칙 칸 + 알림 줄») 정적 검사 + 화면 그림 — 사본 위 · Claude 0 · 볼트 체계·장부에 안 씀 · 창 없음(헤드리스).

사본: 3_시스템/sort/*.json 을 임시 폴더로 · 공지-들이기 사본에 시험용 자동 규칙 a1(제목 «전형» → 확인 필요 · 만든이 «자동 …») ·
     sort.run(진짜 수집글 · 읽기만 · 장부는 임시) · 시험용 사건 «채택» 하나(되돌리기 = 규칙 a1). 사건을 내는 쪽(S5·S2)은 아직 없다.
수집 창: collect_desk.view() 를 진짜 자료로(분류 칸만 사본을 읽게) → view/index.html 을 그대로 띄운 판에 자료를 넣고 출처 «장학»을 고름.
잰다: 첫 화면 문장 0(자료 글 = data-d·글 줄·기록 줄은 뺌) · 폭 760·1000 넘침 0(첫 화면 · 규칙 칸 연 뒤) ·
     누름 수 — 판정(단추 + 확인 = 2) · moa(1) · 알림 되돌리기(1) · 알림 확인(1) · 규칙 줄 되돌리기(규칙 칸 + 줄 단추 = 2) · 단추가 보내는 행위.
그림: 규칙 칸을 연 화면(밝음·어둠) → --shots 폴더 제작-밝음.png · 제작-어둠.png.

  py -3 3_시스템/_eval/sort_desk_check.py [--shots <폴더>] [--source <출처 id>]
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
DESK = os.path.join(VAULT, '.claude', 'skills', 'collect_desk')

PROBE = r"""<script>
(() => {
const DATA = __DATA__, SRC = __SRC__, SHOT = location.search.includes('shot');
const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
const DATA_SEL = '[data-d],.it,.hr,.ev,.chip,.b-h h2,.lr .n,.ch .n,.purpose,.prob,.hx,.link,.moc,.tip,.sm,.flair,.rec';
function sentences() {
  const out = [], tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = tw.nextNode());) {
    const t = n.textContent.replace(/\s+/g, ' ').trim(), el = n.parentElement;
    if (!t || !el || el.closest('script,style,pre') || !vis(el) || el.closest(DATA_SEL)) continue;
    const sp = (t.match(/ /g) || []).length;
    if (t.length >= 10 && (sp >= 3 || /(다|요|까|음|함)[.!?]?$/.test(t) || /[.!?] \S/.test(t))) out.push(t.slice(0, 40));
  }
  return out;
}
function overflow() {
  const out = [];
  for (const el of document.querySelectorAll('#app *')) {
    if (!vis(el) || ![...el.childNodes].some(c => c.nodeType === 3 && c.textContent.trim())) continue;
    const s = getComputedStyle(el);
    if (s.overflowX === 'visible' && s.display !== 'inline' && el.scrollWidth > el.clientWidth + 1) out.push((el.innerText || '').trim().slice(0, 24));
  }
  if (document.documentElement.scrollWidth > innerWidth + 1) out.push('가로 스크롤');
  return out;
}
const sent = [];
addEventListener('message', e => { if (e.data && e.data.t === 'act') sent.push(e.data); });
const q = s => document.querySelector(s), click = el => { el && el.click(); return !!el; };
const wait = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  postMessage({ t: 'data', data: DATA }, '*');
  await wait(30);
  click(q(`[data-sel="${SRC}"]`));
  await wait(30);
  if (SHOT) { click(q('[data-seg="rules"]')); return; }
  const R = { 폭: innerWidth, 고른출처: !!q(`[data-sel="${SRC}"].sel`), 첫화면: { 문장: sentences(), 넘침: overflow() }, 누름: {}, 보냄: [] };
  R.알림줄 = [...document.querySelectorAll('.nt')].map(x => x.innerText.trim());
  R.규칙칸 = (q('[data-seg="rules"]') || {}).innerText || '';
  const judge = q('[data-judge]');
  R.누름.판정 = judge && vis(judge) ? (click(judge), await wait(10), q('.dlg [data-y]') ? 2 : -1) : 0;
  click(q('.dlg [data-n]'));
  const moa = q('[data-moa]');
  R.누름.moa = moa && vis(moa) ? 1 : 0;
  const un = q('.nt [data-sortop="revert"]'), ack = q('.nt [data-sortop="ack"]');
  R.누름.알림되돌리기 = un && vis(un) ? 1 : 0;
  R.누름.알림확인 = ack && vis(ack) ? 1 : 0;
  click(un); click(ack);
  await wait(10);
  click(q('[data-seg="rules"]'));
  await wait(30);
  const ru = q('.rl [data-sortop="rule"]');
  R.누름.규칙되돌리기 = ru ? 2 : 0;
  R.규칙줄 = [...document.querySelectorAll('.rg,.rl')].map(x => x.innerText.replace(/\s+/g, ' ').trim());
  R.규칙칸연뒤 = { 넘침: overflow() };
  click(ru);
  await wait(10);
  R.보냄 = sent.map(m => m.id + ' ' + JSON.stringify(m.args));
  const pre = document.createElement('pre'); pre.id = '결과'; pre.hidden = true; pre.textContent = JSON.stringify(R); document.body.append(pre);
})();
})();
</script>"""


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots', help='그림 폴더(제작-밝음.png · 제작-어둠.png)')
    ap.add_argument('--source', default='school-a')
    a = ap.parse_args()
    T = tempfile.mkdtemp(prefix='sort-desk-')
    try:
        return run(T, a)
    finally:
        shutil.rmtree(T, ignore_errors=True)


def run(T, a):
    import sort
    import draft
    # ── 사본 체계 + 시험용 자동 규칙 · sort.run(장부 = 임시) · 시험용 사건 ──
    sdir, ix = os.path.join(T, 'sort'), os.path.join(T, 'idx')
    if not os.path.isdir(sort.SYSTEMS):     # 새로 받은 볼트 = 분류 체계 0(빈 틀은 sort-examples) — 잴 체계가 없다
        print('건너뜀: 분류 체계 폴더 없음(%s) — 체계를 하나 만든 볼트에서 돈다' % sort.SYSTEMS)
        raise SystemExit(0)
    shutil.copytree(sort.SYSTEMS, sdir)
    p = os.path.join(sdir, '공지-들이기.json')
    s = json.load(open(p, encoding='utf-8'))
    s['규칙'].insert(0, {'id': 'a1', '말': '제목에 «전형»', '만든이': '자동 11-18 · 지지 3 · 그림자 10/10 (시험)',
                        '조건': {'칸': '제목', '맞음': '전형'}, '갈래': '확인 필요', '근거': '제목 «전형»'})
    open(p, 'w', encoding='utf-8').write(sort.dump_system(s))
    sort.SYSTEMS, sort.INDEX = sdir, ix
    sort.reset()
    if sort.check(sdir)['공지-들이기'][0]:
        print('사본 체계 오류', sort.check(sdir)['공지-들이기'][0])
        return 1
    sort.run()
    eid = sort.event_add('공지-들이기', '채택', '제목에 «전형» → 확인 필요', {'규칙': 'a1'})
    # ── 수집 창 자료(진짜 · 분류 칸만 사본) ──
    cd = load('collect_desk_t', os.path.join(DESK, 'scripts', 'collect_desk.py'))
    cd.SORT_SYS, cd.SORT_IX = sdir, ix
    data = cd.view('check')
    # 출처를 안 주면 수집 창 기능의 개인화 파트 «시험 출처»(볼트마다 출처 id 가 다름 · 시험에 개인 출처 id 를 박지 않음 · incident-2026-11-22)
    if not a.source:
        try:
            a.source = json.load(open(os.path.join(DESK, 'personal', 'values.json'), encoding='utf-8')).get('시험 출처') or ''
        except (OSError, ValueError):
            a.source = ''
    src = next((x for x in data['sources'] if x['id'] == a.source), None)
    if not src:
        print(f'출처 없음: {a.source}')
        return 1
    html = open(os.path.join(DESK, 'view', 'index.html'), encoding='utf-8').read()
    probe = PROBE.replace('__DATA__', json.dumps(data, ensure_ascii=False).replace('</', '<\\/')).replace('__SRC__', json.dumps(a.source))
    pages = {}
    for theme in ('light', 'dark'):
        h = html if theme == 'light' else html.replace('@media (prefers-color-scheme:dark)', '@media all')
        pg = Path(T) / f'desk-{theme}.html'
        pg.write_text(h.replace('</body>', probe + '\n</body>'), 'utf-8')
        pages[theme] = pg
    chrome = draft._chrome()
    if not chrome:
        print('크롬·엣지 없음 — 화면 검사 못 함')
        return 1
    bad, res = [], {}
    for w in (760, 1000):
        dom = draft._run(chrome, pages['light'], ['--dump-dom', f'--window-size={w},1400'], None)
        m = re.search(r'<pre id="결과" hidden="">([\s\S]*?)</pre>', dom)
        if not m:
            print(f'폭 {w}: 결과를 못 읽음')
            return 1
        import html as H
        R = json.loads(H.unescape(m.group(1)))
        res[w] = R
        print(f'폭 {w}: 첫 화면 문장 {len(R["첫화면"]["문장"])} · 넘침 {len(R["첫화면"]["넘침"])} · 규칙 칸 연 뒤 넘침 {len(R["규칙칸연뒤"]["넘침"])} · 누름 {R["누름"]}')
        for k in ('문장', '넘침'):
            if R['첫화면'][k]:
                print(f'   {k}: {R["첫화면"][k][:5]}')
        if R['규칙칸연뒤']['넘침']:
            print(f'   규칙 칸 넘침: {R["규칙칸연뒤"]["넘침"][:5]}')
        n = R['누름']
        if R['첫화면']['문장'] or R['첫화면']['넘침'] or R['규칙칸연뒤']['넘침']:
            bad.append(f'{w} 문장·넘침')
        if not (0 < n['판정'] <= 2 and 0 < n['moa'] <= 2 and 0 < n['알림되돌리기'] <= 2 and 0 < n['규칙되돌리기'] <= 2 and n['알림확인'] == 1):
            bad.append(f'{w} 누름 {n}')
    R = res[1000]
    print(f'알림 줄 {R["알림줄"]} · 규칙 칸 «{R["규칙칸"].strip()}»')
    print('규칙 줄 ' + ' | '.join(R['규칙줄']))
    want = [f'collect_desk.sort {{"op":"revert","id":"{eid}"}}', f'collect_desk.sort {{"op":"ack","id":"{eid}"}}', 'collect_desk.sort {"op":"rule","id":"공지-들이기/a1"}']
    sent_ok = R['보냄'] == want
    print(f'보낸 행위 {"맞음" if sent_ok else "다름"} — {R["보냄"]}')
    if not sent_ok:
        bad.append('보낸 행위')
    if a.shots:
        out = Path(a.shots).resolve()          # 크롬은 제 자리에서 돈다 — 상대 경로면 엉뚱한 곳에 씀
        for theme, name in (('light', '제작-밝음.png'), ('dark', '제작-어둠.png')):
            draft._run(chrome, pages[theme], [f'--screenshot={out / name}', '--window-size=1000,640', '--force-device-scale-factor=1.5', '--hide-scrollbars'], '?shot')
            print(f'그림 {out / name} {"있음" if (out / name).exists() else "없음"}')
    print('\n' + ('합격 — 문장 0 · 넘침 0 · 누름 ≤ 2 · 보낸 행위 맞음' if not bad else f'불합격: {bad}'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
