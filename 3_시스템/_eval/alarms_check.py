"""알림 모듈 규칙 시험 — 쓰기 없음(볼트의 일정·설정은 읽기만).
    py -3 3_시스템/_eval/alarms_check.py
"""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alarms  # noqa: E402
import roles  # noqa: E402 — 대기열 사람 줄의 호칭(프로필)
import schedule  # noqa: E402

NOW = dt.datetime(2026, 11, 5, 12, 0, tzinfo=schedule.KST)
SOON = '- [ ] 2026-11-06 (금) 23:59 물리 · 과제 마감 ^lms-asg-1'
FAR = '- [ ] 2026-11-20 (금) 23:59 물리 · 과제 마감'


def rows(*lines, name='내-일정.md'):
    return [(name, i, ln, schedule.LINE.match(ln)) for i, ln in enumerate(lines, 1)]


def at(a):
    return dt.datetime.fromtimestamp(a['at'] / 1000, schedule.KST).strftime('%m-%d %H:%M')


def note(obj):
    return '---\ntitle: x\n---\n# 설정\n\n```json\n' + (obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)) + '\n```\n'


def parsed(obj=None):
    return alarms.parse_settings(None if obj is None else note(obj))


def run(*lines, name='내-일정.md', now=NOW, s=None):
    return alarms.build({'probe': False}, now=now, rows=rows(*lines, name=name), settings=parsed(s))['items']


def pull(st, *lines, now=NOW, queue=(), name='내-일정.md', s=None, notices=()):
    return alarms.build({'probe': False}, now=now, rows=rows(*lines, name=name), st=st, queue=list(queue), settings=parsed(s), notices=list(notices))['items']


def later(**kw):
    return NOW + dt.timedelta(**kw)


class Deadlines(unittest.TestCase):
    def test_three_days_and_one_day_before_at_evening(self):
        got = run(FAR)
        self.assertEqual([at(a) for a in got], ['11-17 20:00', '11-19 20:00'])
        self.assertEqual(got[0]['text'], '3일 뒤 · 11-20 (금) 23:59')
        self.assertEqual(got[1]['text'], '내일 · 11-20 (금) 23:59')

    def test_date_only_is_the_same(self):
        self.assertEqual([at(a) for a in run('- [ ] 2026-11-20 (금) 장학 · 선발 (확인 필요) ^sch-1', name='장학-마감.md')], ['11-17 20:00', '11-19 20:00'])

    def test_passed_ring_times_are_gone(self):
        self.assertEqual([at(a) for a in run(SOON)], ['11-05 20:00'])
        self.assertEqual(run('- [ ] 2026-11-05 (목) 11:00 지남'), [])

    def test_ids_carry_the_date_so_a_moved_line_rings_again(self):
        a = run('- [ ] 2026-11-20 (금) 23:59 물리 · 과제 [[경로|원본]] ^lms-asg-9')
        self.assertEqual(a[0]['id'], 'lms-asg-9@2026-11-20@d3-2000')
        self.assertEqual(a[0]['title'], '물리 · 과제')

    def test_done_and_pending_verdict_are_out(self):
        self.assertEqual(run('- [x] 2026-11-20 (금) 23:59 끝남', '- [ ] 2026-11-20 (금) 장학 · 글 (판정 대기) ^sch-1', name='장학-마감.md'), [])

    def test_files_without_verdict_stay_quiet(self):
        self.assertEqual(run('- [ ] 2026-12-02 (수) 학사일정 · 재입학신청 시작 ^cal-1', name='학사일정.md'), [])


class Custom(unittest.TestCase):
    """사용자가 고치는 칸."""

    def test_days_and_several_times_a_day(self):
        got = run(FAR, s={'기본': {'며칠_전': [7, 1], '시각': ['09:00', '21:30']}})
        self.assertEqual([at(a) for a in got], ['11-13 09:00', '11-13 21:30', '11-19 09:00', '11-19 21:30'])

    def test_same_day_ring(self):
        self.assertEqual([at(a) for a in run(FAR, s={'기본': {'며칠_전': [0], '시각': ['09:00']}})], ['11-20 09:00'])

    def test_add_a_file_with_its_own_rule(self):
        line = '- [ ] 2026-12-02 (수) 학사일정 · 재입학신청 시작 ^cal-1'
        got = run(line, name='학사일정.md', s={'파일': {'학사일정.md': {'며칠_전': [1], '시각': ['10:00']}}})
        self.assertEqual([at(a) for a in got], ['12-01 10:00'])

    def test_turn_a_default_file_off_by_leaving_it_out_or_saying_so(self):
        self.assertEqual(run(FAR, s={'파일': {'LMS-마감.md': {}}}), [])
        self.assertEqual(run(FAR, s={'파일': {'내-일정.md': {'끔': True}, 'LMS-마감.md': {}}}), [])

    def test_subject_rule(self):
        got = run(FAR, s={'과목': {'물리': {'며칠_전': [5]}}})
        self.assertEqual([at(a) for a in got], ['11-15 20:00'])

    def test_one_line_by_its_words(self):
        s = {'글자': [{'포함': '기말', '며칠_전': [14, 7]}, {'포함': '면담', '끔': True}]}
        self.assertEqual([at(a) for a in run('- [ ] 2026-12-20 (일) 전자기 · 기말고사', s=s)], ['12-06 20:00', '12-13 20:00'])
        self.assertEqual(run('- [ ] 2026-12-20 (일) 교수 면담', s=s), [])

    def test_words_can_turn_on_one_line_of_a_quiet_file(self):
        s = {'글자': [{'포함': '수강신청', '끔': False}]}
        self.assertEqual(len(run('- [ ] 2027-01-15 (금) 학사일정 · 수강신청 시작 ^cal-9', name='학사일정.md', s=s)), 2)
        self.assertEqual(run('- [ ] 2027-01-15 (금) 학사일정 · 등록 시작 ^cal-8', name='학사일정.md', s=s), [])

    def test_quiet_hours_can_change_and_be_removed(self):
        s = {'기본': {'며칠_전': [1], '시각': ['23:30']}}
        self.assertEqual([at(a) for a in run(FAR, s=s)], ['11-20 08:00'])
        self.assertEqual([at(a) for a in run(FAR, s={**s, '잘_시간': {'부터': '23:45', '까지': '07:00'}})], ['11-19 23:30'])
        self.assertEqual([at(a) for a in run(FAR, s={**s, '잘_시간': {'부터': '00:00', '까지': '00:00'}})], ['11-19 23:30'])

    def test_morning_too_close_to_the_deadline_rings_before_sleep(self):
        s = {'기본': {'며칠_전': [0], '시각': ['05:00']}}
        self.assertEqual([at(a) for a in run('- [ ] 2026-11-20 (금) 08:30 시험', s=s)], ['11-19 22:00'])

    def test_pull_interval_goes_to_the_phone(self):
        got = alarms.build({'probe': False}, now=NOW, rows=[], settings=parsed({'당겨_오기_분': 45}))
        self.assertEqual(got['pull_minutes'], 45)
        self.assertEqual(alarms.build({'probe': False}, now=NOW, rows=[], settings=parsed({'켬': False}))['pull_minutes'], 30)
        self.assertEqual(alarms.build({'probe': False}, now=NOW, rows=[], settings=parsed({'당겨_오기_분': 5}))['pull_minutes'], 30)

    def test_sleeping_time_goes_to_the_phone(self):
        """폰의 하트비트가 잘 시간에 안 깬다: 설정의 잘_시간 을 그대로 보낸다(기본 23:00~08:00 · 꺼도 · 틀린 값이어도 기본값)."""
        self.assertEqual(alarms.build({'probe': False}, now=NOW, rows=[], settings=parsed({}))['quiet'], ['23:00', '08:00'])
        got = alarms.build({'probe': False}, now=NOW, rows=[], settings=parsed({'잘_시간': {'부터': '00:30', '까지': '07:00'}}))
        self.assertEqual(got['quiet'], ['00:30', '07:00'])
        self.assertEqual(alarms.build({'probe': False}, now=NOW, rows=[], settings=parsed({'잘_시간': {'부터': '00:00', '까지': '00:00'}}))['quiet'], ['00:00', '00:00'])
        self.assertEqual(alarms.build({'probe': False}, now=NOW, rows=[], settings=parsed({'켬': False}))['quiet'], ['23:00', '08:00'])
        # 틀린 칸만 기본값으로(설정 노트의 약속): 부터 는 기본 23:00, 까지 는 쓴 그대로.
        self.assertEqual(alarms.build({'probe': False}, now=NOW, rows=[], settings=parsed({'잘_시간': {'부터': '25:99', '까지': '07:00'}}))['quiet'], ['23:00', '07:00'])

    def test_all_off(self):
        self.assertEqual(run(FAR, s={'켬': False}), [])
        self.assertEqual(alarms.build({}, now=NOW, rows=rows(FAR), st={}, queue=[], settings=parsed({'켬': False}), notices=[])['items'], [])

    def test_rule_can_never_leave_a_line_without_a_ring(self):
        # 시각이 마감 뒤라 규칙대로면 하나도 안 울릴 때 — 마감 한 시간 전에라도
        got = run('- [ ] 2026-11-20 (금) 10:00 시험', s={'기본': {'며칠_전': [0], '시각': ['20:00']}})
        self.assertEqual([at(a) for a in got], ['11-20 09:00'])
        self.assertTrue(got[0]['id'].endswith('@last'))

    def test_defaults_match_the_note_in_the_vault(self):
        s, problems = alarms.load_settings()
        self.assertEqual(problems, [])
        base = alarms.parse_settings(None)[0]
        s.pop('당겨_오기_분'), base.pop('당겨_오기_분')       # 간격은 사용자가 맞추는 값(11-05 45분)이라 기본값과 같게 묶지 않는다
        self.assertEqual(s, base)


class Wrong(unittest.TestCase):
    """잘못 고쳐도 조용히 사라지면 안 된다: 기본값으로 울리고, 틀린 칸을 알린다."""

    BAD = [
        ('글자 깨짐', '{ "기본": '),
        ('블록 없음', None),
        ('맨 바깥이 목록', '[1]'),
        ('며칠 글자', {'기본': {'며칠_전': '3'}}),
        ('며칠 빈 목록', {'기본': {'며칠_전': []}}),
        ('며칠 음수', {'기본': {'며칠_전': [-1]}}),
        ('며칠 참거짓', {'기본': {'며칠_전': [True]}}),
        ('시각 25시', {'기본': {'시각': ['25:00']}}),
        ('시각 숫자', {'기본': {'시각': [20]}}),
        ('시각 빈 목록', {'기본': {'시각': []}}),
        ('기본이 글자', {'기본': '3일'}),
        ('칸 이름 오타', {'기본': {'며칠전': [9]}}),
        ('맨 위 칸 오타', {'기뵨': {'며칠_전': [9]}}),
        ('파일 비움', {'파일': {}}),
        ('파일 목록꼴', {'파일': ['LMS-마감.md']}),
        ('파일 이름 오타', {'파일': {'내일정.md': {}}}),
        ('켬 글자', {'켬': '꺼'}),
        ('잘 시간 글자', {'잘_시간': {'부터': '밤'}}),
        ('바로 칸 오타', {'바로': {'막힘막힘': True}}),
        ('바로 글자', {'바로': {'막힘': '응'}}),
        ('글자 포함 없음', {'글자': [{'며칠_전': [1]}]}),
        ('과목 글자', {'과목': '물리'}),
        ('간격 너무 짧음', {'당겨_오기_분': 5}),
        ('간격 글자', {'당겨_오기_분': '30'}),
    ]

    def build_with(self, bad):
        text = '# 설정\n블록 없음\n' if bad is None else note(bad)
        return alarms.parse_settings(text)

    def test_every_wrong_value_still_rings_on_default_times_and_is_reported(self):
        for name, bad in self.BAD:
            with self.subTest(name):
                got = alarms.build({'probe': False}, now=NOW, rows=rows(FAR), settings=self.build_with(bad))
                self.assertEqual([at(a) for a in got['items']], ['11-17 20:00', '11-19 20:00'], name)
                self.assertTrue(got['problems'], name)

    def test_only_the_wrong_field_falls_back(self):
        s = self.build_with({'기본': {'며칠_전': 'x', '시각': ['09:00']}})
        self.assertEqual([at(a) for a in alarms.build({'probe': False}, now=NOW, rows=rows(FAR), settings=s)['items']], ['11-17 09:00', '11-19 09:00'])

    def test_phone_is_told_once_even_on_first_pull(self):
        st = {}
        s = self.build_with({'기본': {'시각': ['25:00']}})
        first = alarms.build({'probe': False}, now=NOW, rows=[], st=st, queue=[], settings=s, notices=[])['items']
        self.assertEqual(first[0]['title'], '알림 설정 틀림')
        self.assertIn('기본.시각', first[0]['text'])
        again = alarms.build({'probe': False}, now=later(hours=1), rows=[], st=st, queue=[], settings=s, notices=[])['items']
        self.assertEqual(again[0]['id'], first[0]['id'])

    def test_fixing_it_clears_the_warning(self):
        st = {}
        alarms.build({'probe': False}, now=NOW, rows=[], st=st, queue=[], settings=self.build_with({'켬': '꺼'}), notices=[])
        got = alarms.build({'probe': False}, now=later(hours=1), rows=[], st=st, queue=[], settings=parsed(), notices=[])['items']
        self.assertEqual(got, [])

    def test_missing_note_means_defaults_without_a_warning(self):
        s, problems = alarms.load_settings(os.path.join(tempfile.gettempdir(), 'no-such-note-x.md'))
        self.assertEqual(problems, [])
        self.assertEqual(s['기본']['며칠_전'], [3, 1])

    def test_read_fresh_on_every_request(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, '알림-설정.md')
            with open(p, 'w', encoding='utf-8') as f:
                f.write(note({'기본': {'며칠_전': [2]}}))
            self.assertEqual(alarms.load_settings(p)[0]['기본']['며칠_전'], [2])
            with open(p, 'w', encoding='utf-8') as f:
                f.write(note({'기본': {'며칠_전': [5]}}))
            self.assertEqual(alarms.load_settings(p)[0]['기본']['며칠_전'], [5])

    def test_too_many_rings_keeps_the_soonest_and_says_so(self):
        lines = [f'- [ ] 2026-12-{d:02d} (월) 일 {i}' for d in range(10, 29) for i in range(40)]
        got = alarms.build({'probe': False}, now=NOW, rows=rows(*lines), settings=parsed())
        self.assertEqual(len(got['items']), alarms.MAX_ITEMS)
        self.assertTrue(any('앞 400개만' in p for p in got['problems']))


class RightAway(unittest.TestCase):
    def events(self, items):
        return [a for a in items if a['id'].startswith('ev-')]

    def test_first_pull_rings_nothing_extra(self):
        self.assertEqual(self.events(pull({}, SOON, queue=[('2026-11-05 10:00', '로그인 끊김')])), [])

    def test_new_line_past_three_days_rings_now_and_one_day_before(self):
        st = {}
        pull(st)
        got = pull(st, SOON)
        self.assertEqual([at(a) for a in got], ['11-05 12:00', '11-05 20:00'])
        self.assertEqual(got[0]['id'][:8], 'ev-late-')

    def test_new_line_before_three_days_just_gets_its_times(self):
        st = {}
        pull(st)
        self.assertEqual(self.events(pull(st, FAR)), [])

    def test_new_line_one_day_away_rings_now_only(self):
        st = {}
        pull(st)
        self.assertEqual([at(a) for a in pull(st, '- [ ] 2026-11-05 (목) 15:00 곧')], ['11-05 12:00'])

    def test_a_known_line_past_three_days_stays_quiet(self):
        st = {}
        pull(st, SOON)
        self.assertEqual(self.events(pull(st, SOON, now=later(hours=1))), [])

    def test_moved_date_rings_now_and_new_times(self):
        st = {}
        pull(st, '- [ ] 2026-12-17 (목) 18:00 전자기 · 기말 ^lms-asg-7')
        got = pull(st, '- [ ] 2026-12-10 (목) 18:00 전자기 · 기말 ^lms-asg-7', now=later(hours=1))
        ev = self.events(got)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]['id'][:9], 'ev-moved-')
        self.assertEqual(ev[0]['text'], '12-17 → 12-10 (목) 18:00')
        self.assertIn('lms-asg-7@2026-12-10@d3-2000', [a['id'] for a in got])
        self.assertNotIn('lms-asg-7@2026-12-17@d3-2000', [a['id'] for a in got])

    def test_hand_line_moved_is_found_by_its_text(self):
        st = {}
        pull(st, '- [ ] 2026-12-17 (목) 면담')
        self.assertEqual(self.events(pull(st, '- [ ] 2026-12-18 (금) 면담', now=later(hours=1)))[0]['text'], '12-17 → 12-18 (금)')

    def test_same_text_on_two_dates_is_not_a_move(self):
        st = {}
        pull(st, '- [ ] 2026-12-17 (목) 수업', '- [ ] 2026-12-24 (목) 수업')
        self.assertEqual(self.events(pull(st, '- [ ] 2026-12-24 (목) 수업', now=later(hours=1))), [])

    def test_blocked_rings_once_per_queue_line(self):
        st = {}
        pull(st)
        q = [('2026-11-05 11:50', '로그인 끊김 — 다시 로그인')]
        got = pull(st, queue=q, now=later(hours=1))
        self.assertEqual((got[0]['title'], at(got[0])), ('수집 막힘', '11-05 13:00'))
        self.assertEqual(self.events(pull(st, queue=q, now=later(hours=2))), self.events(got))

    def test_same_blocked_reason_from_two_sources_rings_once(self):
        # 리허설(11-06): 구독 아님·사용량 경고는 출처마다 같은 말을 대기열에 적는다 — 폰에 같은 알림이 줄줄이 뜨면 안 된다
        st = {}
        pull(st)
        q = [('2026-11-05 11:50', '자동 추출 안 함 — 멈춤: 구독 아님'), ('2026-11-05 11:50', '자동 추출 안 함 — 멈춤: 구독 아님'), ('2026-11-05 11:51', '목록 1쪽 받기 실패')]
        got = [a['text'] for a in self.events(pull(st, queue=q, now=later(hours=1)))]
        self.assertEqual(sorted(got), ['목록 1쪽 받기 실패', '자동 추출 안 함 — 멈춤: 구독 아님'])

    def test_quiet_hours_wait_for_the_morning(self):
        st = {}
        night = dt.datetime(2026, 11, 5, 23, 30, tzinfo=schedule.KST)
        pull(st, now=night)
        self.assertEqual(at(pull(st, queue=[('t', '로그인 끊김')], now=night)[0]), '11-06 08:00')

    def test_vanishing_for_one_pull_does_not_ring_again(self):
        st = {}
        pull(st, SOON)
        pull(st, now=later(hours=1))
        self.assertEqual(self.events(pull(st, SOON, now=later(hours=2))), [])

    def test_events_expire(self):
        st = {}
        pull(st)
        pull(st, SOON)
        self.assertEqual(self.events(pull(st, SOON, now=later(days=8))), [])

    def test_kinds_can_be_turned_off(self):
        st = {}
        pull(st)
        self.assertEqual(self.events(pull(st, SOON, s={'바로': {'늦게_앎': False}})), [])

    OLD = ('2026-10-01 옛 공지', '옛 공지', '2026-10-01')
    NEW = ('2026-11-05 새 공지', '새 공지 하나', '2026-11-05')

    def test_new_notice_rings_by_default_and_only_once(self):
        st = {}
        self.assertEqual(self.events(pull(st, notices=[self.OLD])), [])         # 첫 실행: 지난 공지를 몰아 울리지 않는다
        got = self.events(pull(st, notices=[self.OLD, self.NEW], now=later(hours=1)))
        self.assertEqual([(a['title'], a['text']) for a in got], [('새 공지 하나', '새 공지')])
        again = self.events(pull(st, notices=[self.OLD, self.NEW], now=later(hours=2)))
        self.assertEqual(again, got)                                             # 같은 사건(앱이 id 로 한 번만 울린다)

    def test_first_pull_with_a_recent_notice_stays_quiet(self):
        self.assertEqual(self.events(pull({}, notices=[self.NEW])), [])

    def test_new_notice_can_be_turned_off_and_does_not_flood_when_turned_on(self):
        st = {}
        pull(st)
        off = {'바로': {'새_공지': False}}
        self.assertEqual(self.events(pull(st, notices=[self.NEW], now=later(hours=1), s=off)), [])
        self.assertEqual(self.events(pull(st, notices=[self.NEW], now=later(hours=2))), [])

    def test_old_posts_from_a_new_source_stay_quiet(self):
        st = {}
        pull(st)
        self.assertEqual(self.events(pull(st, notices=[('2026-09-01 글', '글', '2026-09-01')], now=later(hours=1))), [])

    def test_many_at_once_become_one_ring(self):
        st = {}
        pull(st)
        many = [(f'2026-11-05 글{i}', f'글{i}', '2026-11-05') for i in range(5)]
        got = self.events(pull(st, notices=many, now=later(hours=1)))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]['title'], '새 공지 5건')
        self.assertEqual(len(self.events(pull(st, notices=many, now=later(hours=2)))), 1)

    def test_moved_file_does_not_ring_again(self):
        st = {}
        pull(st)
        pull(st, notices=[self.NEW], now=later(hours=1))
        got = pull(st, notices=[self.NEW], now=later(days=8))        # 사건이 사라진 뒤에도
        self.assertEqual(self.events(got), [])

    def test_notice_and_its_deadline_line_ring_once_together(self):
        st = {}
        pull(st)
        n = ('2026-11-05 [교외-11_06]재단 장학생 선발', '[교외-11_06]재단 장학생 선발', '2026-11-05')
        line = '- [ ] 2026-11-06 (금) 장학 · 재단 장학생 선발 (확인 필요) ^sch-7'
        got = self.events(pull(st, line, name='장학-마감.md', notices=[n], now=later(hours=1)))
        self.assertEqual([a['id'][:9] for a in got], ['ev-notice'])

    def test_turning_a_file_on_later_does_not_ring_everything_at_once(self):
        st = {}
        line = '- [ ] 2026-11-06 (금) 학사일정 · 무언가 ^cal-1'
        pull(st, line, name='학사일정.md')
        got = pull(st, line, name='학사일정.md', now=later(hours=1), s={'파일': {'학사일정.md': {}}})
        self.assertEqual(self.events(got), [])

    def test_verdict_arriving_late_counts_as_new(self):
        st = {}
        pull(st, '- [ ] 2026-11-06 (금) 장학 · 글 (판정 대기) ^sch-5', name='장학-마감.md')
        got = pull(st, '- [ ] 2026-11-06 (금) 장학 · 글 (확인 필요) ^sch-5', name='장학-마감.md', now=later(hours=1))
        self.assertEqual(self.events(got)[0]['id'][:8], 'ev-late-')

    def test_queue_line_format_matches_the_collector(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'q.md')
            with open(p, 'w', encoding='utf-8') as f:
                me = roles.me()
                f.write(f'- [ ] 2026-11-05 10:00:00 `run1` ({me}) 로그인 끊김\n- [ ] 2026-11-05 10:00:00 `run2` (Claude) 구조 바뀜\n- [ ] 2026-11-05 10:00:00 `run3` ({me}·Claude) 첨부 격리\n- [x] 2026-11-04 10:00:00 `run0` ({me}) 끝남\n')
            self.assertEqual(alarms.blocked_lines(p), [('2026-11-05 10:00:00', '로그인 끊김')])


class Probes(unittest.TestCase):
    def test_three_quiet_nights_ahead(self):
        got = alarms.build({}, now=NOW, rows=[], settings=parsed())['items']
        self.assertEqual([a['id'] for a in got], ['probe-20261106', 'probe-20261107', 'probe-20261108'])
        self.assertEqual(at(got[0]), '11-06 03:17')
        self.assertTrue(all(a['probe'] for a in got))

    def test_can_be_turned_off(self):
        self.assertEqual(alarms.build({'probe': False}, now=NOW, rows=[], settings=parsed())['items'], [])

    def test_mode_comes_from_config_only(self):
        self.assertNotIn('mode', alarms.build({}, now=NOW, rows=[], settings=parsed())['items'][0])
        self.assertEqual(alarms.build({'mode': 'clock'}, now=NOW, rows=[], settings=parsed())['items'][0]['mode'], 'clock')


if __name__ == '__main__':
    unittest.main(verbosity=0)
