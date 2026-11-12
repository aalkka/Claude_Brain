# -*- coding: utf-8 -*-
"""수집 추가·고침 시험(11-06 collect-add) — 탐색·미리보기(저장 없음)·확정·낱말 관문·깨짐 → «실패»·고침을 진짜 코드 경로로 잰다.
임시 볼트 · 내 컴퓨터 안 시험 서버(게시판·RSS·유튜브 꼴 Atom·robots) · 볼트 수집 설정을 안 쓴다. 실행: py -3 3_시스템/_eval/collect_add_check.py"""
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.dirname(HERE)
VAULT_REAL = os.path.dirname(REAL)
root = tempfile.mkdtemp(prefix='add-')
V = os.path.join(root, 'vault')
S = os.path.join(V, '3_시스템')
for d in (os.path.join(S, 'collect'), os.path.join(S, 'lms'), os.path.join(S, '_index', 'collect', 'draft')):
    os.makedirs(d)
for f in ('fileops.py', 'roles.py', 'roles.json', 'web-collect.py', 'brain.py', 'actions.json', 'claude_bin.py'):
    shutil.copy2(os.path.join(REAL, f), os.path.join(S, f))
shutil.copytree(os.path.join(VAULT_REAL, '.claude', 'skills', 'collect_desk'), os.path.join(V, '.claude', 'skills', 'collect_desk'),
                ignore=shutil.ignore_patterns('__pycache__'))
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', FILEOPS_NO_OBSIDIAN='1', LMS_AUTO_STATE=os.path.join(root, 'lms-state'), COLLECT_SITE_GAP='0')   # 사이트 1분 간격은 끝에서 2초로 따로 잰다
DRAFT = os.path.join(S, '_index', 'collect', 'draft')
QUEUE = os.path.join(S, '_index', '수집-대기열.md')
res, hits, mode = [], [], {'broken': False}

BOARD = [(305, '2026-11-05', '[모집] 인공지능 동아리 신입 모집'), (304, '2026-11-04', '[행사] 반도체 세미나 안내'), (303, '2026-11-03', '식당 휴무 안내'),
         (302, '2026-11-02', '[모집] 반도체 연구실 학부연구생'), (301, '2026-10-01', '[행사] 지난달 행사')]
ITEMS = [('a1', '2026-11-05', 'GPU 커널 최적화 이야기'), ('a2', '2026-11-03', '오늘의 브이로그'), ('a3', '2026-10-01', 'GPU 오래된 글')]
LONG = [(400 + i, f'2026-10-{i + 1:02d}', f'[세미나] 긴 제목 {i:02d} — Engineering Electronic Transport in Two-Dimensional Materials: From Semiconductors to Superconductors')
        for i in range(20)]     # 11-06 끝까지 시험의 물리학과 세미나 꼴(한 쪽 20줄 · 머리말이 제목 앞을 먹는다)


class Srv(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        hits.append(self.path)
        p, ct, code = self.path, 'text/html; charset=utf-8', 200
        if p == '/robots.txt':
            body, ct = 'User-agent: *\nDisallow: /private\n', 'text/plain'
        elif p.startswith('/board') or p.startswith('/long'):
            tr = ''.join(f'<tr><td class="no">{i}</td><td class="{"t2" if mode["broken"] else "t"}"><a href="/view?id={i}">{t}</a></td><td class="d">{d}</td></tr>'
                         for i, d, t in (LONG if p.startswith('/long') else BOARD))
            body = f'<html><head><title>게시판</title></head><body><table>{tr}</table></body></html>'
        elif p.startswith('/view'):
            i = p.split('=')[-1]
            t = next((t for n, _, t in BOARD if str(n) == i), '?')
            body = f'<div class="v"><h3 class="tit">{t}</h3><span class="date">2026-11-05</span><div class="con"><p>본문 {i} 내용입니다.</p></div></div>'
        elif p == '/feed':
            it = ''.join(f'<item><title>{t}</title><guid>{g}</guid><link>http://x/{g}</link><pubDate>{d}</pubDate><description>본문 {g}</description></item>' for g, d, t in ITEMS)
            body, ct = f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>블로그</title>{it}</channel></rss>', 'application/rss+xml'
        elif p == '/yt':
            en = ''.join(f'<entry><id>yt:video:{g}</id><title>{t}</title><link rel="alternate" href="https://www.youtube.com/watch?v={g}"/><published>{d}T09:00:00+00:00</published>'
                         f'<media:group><media:title>{t}</media:title><media:description>설명 {g}</media:description></media:group></entry>' for g, d, t in ITEMS)
            body = ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" '
                    f'xmlns="http://www.w3.org/2005/Atom"><title>채널</title>{en}</feed>')
            ct = 'application/atom+xml; charset=utf-8'
        elif p == '/blog':   # 머리엔 댓글 피드만 · 본 피드는 본문 링크(워드프레스 글 쪽 꼴 · 11-06 Quanta 에서 잼)
            body = ('<html><head><title>블로그</title><link rel="alternate" type="application/rss+xml" title="블로그 &raquo; Comments Feed" href="/blog/comments/feed/">'
                    '</head><body><a href="/feed">RSS</a> <a href="/about">소개</a> <a href="https://other.example/x/feed/">남의 피드</a></body></html>')
        elif p == '/channel':
            body = '<html><head><title>채널</title><link rel="alternate" type="application/rss+xml" title="RSS" href="/yt"></head><body>채널</body></html>'
        elif p.startswith('/private'):
            body = '<html><body><table><tr><td class="no">9</td><td class="t"><a href="/view?id=9">비밀</a></td><td class="d">2026-11-05</td></tr></table></body></html>'
        else:
            body, code = 'no', 404
        b = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Srv)
threading.Thread(target=srv.serve_forever, daemon=True).start()
U = f'http://127.0.0.1:{srv.server_address[1]}'


def ok(name, cond, extra=''):
    res.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + (f' — {extra}' if extra and not cond else ''))


def run(*args):
    r = subprocess.run([sys.executable, *args], cwd=V, env=ENV, capture_output=True, encoding='utf-8', errors='replace')
    return r.returncode, r.stdout + r.stderr


def br(action, *kv, env=None):
    if env:
        r = subprocess.run([sys.executable, os.path.join(S, 'brain.py'), 'run', action, *kv], cwd=V, env=env, capture_output=True, encoding='utf-8', errors='replace')
        return r.returncode, r.stdout + r.stderr
    return run(os.path.join(S, 'brain.py'), 'run', action, *kv)


def desk():
    return json.loads(run(os.path.join(V, '.claude', 'skills', 'collect_desk', 'scripts', 'collect_desk.py'), 'view')[1].strip().splitlines()[-1])


def draft(rc):
    with open(os.path.join(DRAFT, rc['id'] + '.json'), 'w', encoding='utf-8') as f:
        json.dump(rc, f, ensure_ascii=False)


def vault_files():
    out = set()
    for d, _, fs in os.walk(V):
        if os.sep + '_index' in d or os.sep + '.claude' in d or os.sep + 'ledger' in d:
            continue
        out |= {os.path.join(d, f) for f in fs if not f.endswith('.pyc')}
    return out


BOARD_RC = {'id': 't-board', 'name': '시험 게시판', 'purpose': '반도체·인공지능 모집과 행사만', 'family': 'regex', 'page': U + '/board',
            'list': {'page_url': U + '/board?page={page}', 'pages': 1, 'row': '<tr>(.*?)</tr>',
                     'fields': {'id': '<td class="no">(\\d+)</td>', 'title': '<td class="t"><a[^>]*>(.*?)</a>', 'date': '<td class="d">(.*?)</td>'}},
            'view': {'url': U + '/view?id={id}', 'title': '<h3 class="tit">(.*?)</h3>', 'body': '<div class="con">(.*?)</div>', 'meta': {'등록일자': '<span class="date">(.*?)</span>'}},
            'date_field': '등록일자', 'words': {'keep': '반도체|인공지능', 'skip': '지난달'}, 'recheck_hours': 12, 'first_since': '2026-10-20',
            'folder': '@sources/웹/시험게시판'}

# ── 탐색 ──
before = vault_files()
code, out = br('collect_desk.probe', f'url={U}/channel')
ok('탐색: 채널 쪽에서 피드 찾음', code == 0 and f'{U}/yt' in out, out)
code, out = br('collect_desk.probe', f'url={U}/blog')
ok('탐색: 댓글 피드는 따로 · 본문 링크 피드는 후보(같은 사이트 먼저)', code == 0 and '피드: 없음' in out and f'댓글 피드(글 목록 아님): {U}/blog/comments/feed/' in out
   and f'본문 링크의 피드 꼴 주소(안 받아 봄): {U}/feed · https://other.example/x/feed/' in out and '/about' not in out, out)
ok('탐색: robots 허용', 'robots: 허용' in out, out)
code, out = br('collect_desk.probe', f'url={U}/private/list')
ok('탐색: robots 막힌 쪽은 «막힘» · 받지 않음', code != 0 and 'robots: 막힘' in out and '/private/list' not in hits, out)
code, out = br('collect_desk.probe', f'url={U}/private/list', '--', '--robots-note', '사용자 시험 결정')
ok('탐색: 사용자 결정이 있으면 받음', code == 0 and '/private/list' in hits, out)
code, out = br('collect_desk.probe', f'url={U}/yt')
ok('탐색: 피드 주소면 글 수', '이 주소가 피드(글 3)' in out, out)
robots_hits = sum(1 for h in hits if h == '/robots.txt')
ok('robots.txt 는 하루 캐시(사이트당 1번)', robots_hits == 1, str(robots_hits))

# ── 게시판: 미리보기 → 확정 ──
draft(BOARD_RC)
code, out = br('collect_desk.try', 'id=t-board')
ok('미리보기: 목록 5건 · 통과 3(남길 말·뺄 말)', '목록 1쪽 5건 · 통과 3 · 거름 2' in out, out)
ok('미리보기: 거른 까닭이 줄에', '[거름: 남길 말 없음]' in out and '[거름: 뺄 말 «지난달»]' in out, out)
code, out = br('collect_desk.add', 'id=t-board')
ok('확정 거절: 글 하나 미리보기 전', code != 0 and '글 하나 미리보기' in out, out)
code, out = br('collect_desk.try', 'id=t-board', '--', '--view')
ok('미리보기 --view: 글 제목·본문', code == 0 and '글 하나: [모집] 인공지능 동아리 신입 모집 · 본문' in out, out)
BOARD_RC['words']['skip'] = '지난달|휴무'
draft(BOARD_RC)
code, out = br('collect_desk.add', 'id=t-board')
ok('확정 거절: 미리보기 뒤 초안이 바뀜', code != 0 and '초안이 바뀜' in out, out)
n_view = sum(1 for h in hits if h.startswith('/view'))
code, out = br('collect_desk.try', 'id=t-board')
ok('낱말만 고친 뒤 목록만 다시 봐도 글 확인이 산다(글 요청 0)', code == 0 and sum(1 for h in hits if h.startswith('/view')) == n_view, out)
ok('미리보기는 볼트에 아무것도 안 씀', vault_files() == before and not os.path.exists(os.path.join(S, '_index', 'collect', 't-board.json')))
ok('확정 전에는 조리법이 없다(수집이 안 돈다)', not os.path.exists(os.path.join(S, 'collect', 't-board.json')))
# 미리보기 뒤 결과에 안 닿는 칸만 바꿈 — 사이트를 다시 받지 않고 확정 · 꼴은 다시 본다(11-06 끝까지 시험: 5단계에서 주기만 바꿨는데 확정이 막혀 게시판을 다시 받았다)
draft(dict(BOARD_RC, folder='@없는역할/시험'))
code, out = br('collect_desk.add', 'id=t-board')
ok('확정 거절: 미리보기 뒤 자리를 못 푸는 값으로 바꿈(꼴 검사 · 망 요청 0)', code != 0 and '초안 꼴' in out and 'folder' in out, out)
BOARD_RC.update(recheck_hours=24, name='시험 게시판(주기 바꿈)', first_since='2026-10-25')
draft(BOARD_RC)
n_board = sum(1 for h in hits if h.startswith('/board'))
code, out = br('collect_desk.add', 'id=t-board')
rp = os.path.join(S, 'collect', 't-board.json')
ok('확정: 조리법 생김 · 초안 지움', code == 0 and os.path.exists(rp) and not os.path.exists(os.path.join(DRAFT, 't-board.json')), out)
rc = json.load(open(rp, encoding='utf-8'))
ok('확정: 주기·이름·첫 날만 바꾼 초안은 다시 받지 않고 그 값으로', sum(1 for h in hits if h.startswith('/board')) == n_board and rc.get('recheck_hours') == 24
   and rc.get('name') == '시험 게시판(주기 바꿈)', f'{n_board}→{sum(1 for h in hits if h.startswith("/board"))} {rc.get("recheck_hours")}')
ok('확정: 계약 문구(사용자 · 목적 · robots)', '사용자 수집 창 «수집 추가» 확정' in rc.get('contract', '') and 'robots 허용' in rc['contract'], rc.get('contract'))
ok('확정: 시각 없는 초안 = 주기(15분 확인) · at 칸 없음', 'at' not in rc and '24시간마다(15분 확인)' in out, out[-120:])
draft(BOARD_RC)
code, out = br('collect_desk.add', 'id=t-board')
ok('확정 거절: 같은 id', code != 0 and '이미 있음' in out, out)
os.remove(os.path.join(DRAFT, 't-board.json'))
d = desk()
row = next((s for s in d['sources'] if s['id'] == 't-board'), None)
ok('수집 창에 새 줄(«구독» 묶음 · 남길 말·뺄 말 칩)', row and row['group'] == '구독' and row['keep'] == ['반도체', '인공지능'] and row['skip'] == ['지난달', '휴무'], str(row and {k: row[k] for k in ('group', 'keep', 'skip')}))
ok('일어난 일에 «추가»', row and any(e['s'] == '추가' and e.get('me') for e in row['events']), str(row and row['events']))

# ── 진짜 돌림: 낱말 관문 ──
code, out = run(os.path.join(S, 'web-collect.py'), '--source', 't-board', '--force')
st = json.load(open(os.path.join(S, '_index', 'collect', 't-board.json'), encoding='utf-8'))
inv = [k for k, v in st['items'].items() if v.get('path')]
gate = {k: v.get('why') for k, v in st['items'].items() if v.get('verdict')}
ok('돌림: 관문 통과 3편만 볼트로', sorted(inv) == ['302', '304', '305'], f'{inv} {out[-300:]}')
ok('돌림: 걸린 글은 장부 한 줄(본문 안 받음 · 뺄 말이 남길 말보다 먼저)', gate == {'303': '뺄 말 «휴무»', '301': '뺄 말 «지난달»'}, str(gate))
ok('돌림: 걸린 글의 글 쪽은 안 받음', not any(h in ('/view?id=303', '/view?id=301') for h in hits), str(hits))
d = desk()
row = next(s for s in d['sources'] if s['id'] == 't-board')
ok('수집 창 칸: 볼트 3 · 장부 2', row['cnt']['vault'] == 3 and row['cnt']['ledger'] == 2, str(row['cnt']))

# ── 낱말 칩 고치기(수집 창 set) ──
code, out = br('collect_desk.set', 'source=t-board', 'field=keep+', 'value=모집')
code2, out2 = br('collect_desk.set', 'source=t-board', 'field=skip-', 'value=휴무')
rc = json.load(open(rp, encoding='utf-8'))
ok('칩: 남길 말 더함·뺄 말 뺌 = words', code == 0 and code2 == 0 and rc['words'] == {'keep': '반도체|인공지능|모집', 'skip': '지난달'}, f'{out}{out2}{rc.get("words")}')

# ── 깨짐 → «실패» + 고침 ──
mode['broken'] = True
code, out = run(os.path.join(S, 'web-collect.py'), '--source', 't-board', '--force')
d = desk()
row = next(s for s in d['sources'] if s['id'] == 't-board')
ok('깨짐: 대기열 줄 → 수집 창 «실패»(problems) + 고침 표시', row['problems'] and row['fix'] is True and '제목 못 찾음' in row['problems'][0]['s'], str(row['problems']))
bad = dict(rc, words={'keep': '반도체'})
draft(bad)
br('collect_desk.try', 'id=t-board', '--', '--view')
code, out = br('collect_desk.fix', 'id=t-board')
ok('고침 거절: 구조 밖 칸(words)', code != 0 and '구조 칸만' in out and 'words' in out, out)
good = json.loads(json.dumps(rc))
good['list']['fields']['title'] = '<td class="t2"><a[^>]*>(.*?)</a>'
draft(good)
code, out = br('collect_desk.try', 'id=t-board', '--', '--view')
ok('고침 미리보기: 이미 받은 글과 겹침', '이미 받은 글 5/5' in out, out)
code, out = br('collect_desk.fix', 'id=t-board')
d = desk()
row = next(s for s in d['sources'] if s['id'] == 't-board')
ok('고침: 조리법 교체 · 대기열 줄 닫힘 · «실패» 사라짐', code == 0 and not row['problems'] and not row['fix'], out + str(row['problems']))
ok('고침: 일어난 일에 «고침»', any(e['s'] == '고침' for e in row['events']), str(row['events']))
ok('대기열 줄은 [x] 로(지우지 않음)', '- [x]' in open(QUEUE, encoding='utf-8').read())
fresh = json.loads(json.dumps(good))
fresh['list']['fields']['id'] = '<td class="no">(\\d)\\d+</td>'      # 글 번호 꼴이 바뀐 고침 = 다 새 글로 받힘
draft(fresh)
code, out = br('collect_desk.try', 'id=t-board')
ok('고침 미리보기: 번호 꼴이 바뀌면 문제로 멈춤', code != 0 and '하나도 안 겹침' in out, out)
code, out = br('collect_desk.fix', 'id=t-board')
ok('고침 거절: 그 미리보기는 통과 못 함', code != 0, out)
os.remove(os.path.join(DRAFT, 't-board.json'))

# ── RSS · 유튜브 꼴 ──
for rid, feed, fam_name in (('t-blog', '/feed', 'RSS'), ('t-yt', '/yt', '유튜브 꼴 Atom')):
    draft({'id': rid, 'name': fam_name, 'purpose': 'GPU 글만', 'family': 'rss', 'page': U + '/channel', 'feed': U + feed,
           'words': {'keep': 'gpu'}, **({'at': ['18:00']} if rid == 't-blog' else {'recheck_hours': 12}), 'first_since': '2026-10-20', 'folder': '@sources/웹/' + rid})
    code, out = br('collect_desk.try', f'id={rid}')
    ok(f'{fam_name} 미리보기: 3건 · 통과 2(대소문자 무시)', code == 0 and '목록 1쪽 3건 · 통과 2 · 거름 1' in out, out)
    code, out = br('collect_desk.add', f'id={rid}')
    ok(f'{fam_name} 확정(글 쪽 요청 없는 가족은 --view 없이)', code == 0, out)
    if rid == 't-blog':     # 받기 시각 = Claude 가 정함(11-12) — 확정이 at_since 를 쓰고 시각 예약을 맞춘다
        rb = json.load(open(os.path.join(S, 'collect', rid + '.json'), encoding='utf-8'))
        ok('확정: 시각 초안 = at [18:00] · at_since · «매일 18:00(시각 예약)»', rb.get('at') == ['18:00'] and rb.get('at_since') and 'recheck_hours' not in rb and '매일 18:00' in out, (rb.get('at'), out[-120:]))
    run(os.path.join(S, 'web-collect.py'), '--source', rid, '--force')
    st = json.load(open(os.path.join(S, '_index', 'collect', rid + '.json'), encoding='utf-8'))
    inv = {k: v for k, v in st['items'].items() if v.get('path')}
    ok(f'{fam_name} 첫 돌림: first_since 뒤 + 남길 말 = 1편', len(inv) == 1, str({k: (v.get('title'), v.get('why')) for k, v in st['items'].items()}))
    if inv:
        md = open(os.path.join(V, list(inv.values())[0]['path']), encoding='utf-8').read()
        ok(f'{fam_name} 본문이 글에 든다', ('설명 a1' if rid == 't-yt' else '본문 a1') in md, md[-300:])

# ── robots 막힌 출처 ──
draft(dict(BOARD_RC, id='t-private', page=U + '/private', list=dict(BOARD_RC['list'], page_url=U + '/private?page={page}')))
n_priv = sum(1 for h in hits if h.startswith('/private?'))
code, out = br('collect_desk.try', 'id=t-private', '--', '--view')
ok('robots 막힘: 미리보기가 받지 않고 멈춤', code != 0 and '목록 막힘' in out and sum(1 for h in hits if h.startswith('/private?')) == n_priv, out)
code, out = br('collect_desk.add', 'id=t-private')
ok('확정 거절: robots 막힘 + 사용자 결정 없음', code != 0, out)
rcp = dict(BOARD_RC, id='t-private', page=U + '/private', list=dict(BOARD_RC['list'], page_url=U + '/private?page={page}'), robots_note='사용자 11-06 시험 결정')
draft(rcp)
code, out = br('collect_desk.try', 'id=t-private', '--', '--view')
code, out = br('collect_desk.add', 'id=t-private')
rc = json.load(open(os.path.join(S, 'collect', 't-private.json'), encoding='utf-8')) if code == 0 else {}
ok('robots 막힘 + 사용자 결정 = 확정 · 계약에 결정', code == 0 and 'robots 막힘(사용자 11-06 시험 결정)' in rc.get('contract', ''), out + str(rc.get('contract')))

# ── 미리보기 표 = 줄 전부·제목 전체(11-06 끝까지 시험: 15줄·60자로 잘려 대화가 원시를 뒤지고 엔진을 직접 불렀다) ──
mode['broken'] = False      # 앞 «깨짐» 단계가 바꾼 목록 꼴을 되돌림
lr = dict(BOARD_RC, id='t-long', page=U + '/long', list=dict(BOARD_RC['list'], page_url=U + '/long?page={page}'))
lr.pop('words')
draft(lr)
code, out = br('collect_desk.try', 'id=t-long')
ok('미리보기 표: 20줄 전부 · 긴 제목 전체', code == 0 and '20. 2026-10-20' in out and all(t in out for _, _, t in LONG), out[-500:])

# ── 같은 사이트 1분 간격(시험은 5초 · 파이썬 세 겹 기동이 1~2초라 그보다 길게) — 행위가 남은 만큼 기다렸다 받는다 ──
GAPENV = dict(ENV, COLLECT_SITE_GAP='5')
br('collect_desk.try', 'id=t-long', env=GAPENV)
n_long = sum(1 for h in hits if h.startswith('/long'))
t_a = __import__('time').time()
code, out = br('collect_desk.try', 'id=t-long', env=GAPENV)
t_b = __import__('time').time()
ok('사이트 간격: 곧바로 다시 미리보기하면 기다린 뒤 받음(받기는 한 번)', code == 0 and '초 기다린 뒤 받음' in out and t_b - t_a >= 3
   and sum(1 for h in hits if h.startswith('/long')) == n_long + 1, f'{t_b - t_a:.1f}초 · {out[:160]}')
os.remove(os.path.join(DRAFT, 't-long.json'))

# ── 전체 끔이어도 탐색·미리보기는 사람이 부른 것 ──
json.dump({'all_off': True}, open(os.path.join(S, 'collect.local.json'), 'w', encoding='utf-8'))
code, out = br('collect_desk.probe', f'url={U}/channel')
ok('전체 끔에도 탐색은 돈다', code == 0 and '피드:' in out, out)

srv.shutdown()
shutil.rmtree(root, ignore_errors=True)
n = sum(1 for _, x in res if x)
print(f'\n{n}/{len(res)} 통과')
sys.exit(0 if n == len(res) else 1)
