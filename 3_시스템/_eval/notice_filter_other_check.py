"""notice-filter.py other()·전공 규칙 시험(11-05 장학 대조에서 뽑은 꼴) — 카드 값으로 풀리고, 값이 없으면 모름을 유지하는지.
  py -3 3_시스템/_eval/notice_filter_other_check.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
sys.path.insert(0, SYS)
spec = importlib.util.spec_from_file_location("nf", os.path.join(SYS, "notice-filter.py"))
nf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nf)

ME = {"병역": "마침", "장학수혜": [], "편입생": False, "출생": "2004-05-05", "휴학계획_2027-1": False, "학과": "물리학과", "단과대": "이과대학"}
BLANK = {k: v for k, v in ME.items() if k not in ("편입생", "출생", "휴학계획_2027-1", "장학수혜")}
CASES = [  # (조건 글, 카드, 기대)
    ("편입생 제외", ME, "충족"), ("편입생 제외", BLANK, "모름"), ("편입생 제외", dict(ME, 편입생=True), "불충족"),
    ("신·편입생 제외, 신청 시작일 기준 잔여 정규학기 1개 학기 이상 (일상회복 트랙)", ME, "모름"),
    ("2027학년도 1학기 휴학 계획 없음", ME, "충족"), ("2027학년도 1학기 휴학 계획 없음", BLANK, "모름"), ("2027학년도 1학기 휴학 계획 없음", dict(ME, **{"휴학계획_2027-1": True}), "불충족"),
    ("만 24세 이하(2003년 1월 1일 이후 출생), 군필자는 군복무기간 제외", ME, "충족"), ("만 24세 이하(2003년 1월 1일 이후 출생), 군필자는 군복무기간 제외", BLANK, "모름"),
    ("만 24세 이하(2003년 1월 1일 이후 출생), 군필자는 군복무기간 제외", dict(ME, 출생="2001-01-01"), "모름"),
    ("만 29세 이하 (1997년 1월 1일 이후 출생자)", dict(ME, 출생="1990-01-01", 병역="미필"), "불충족"),
    ("만 24세 이하(2003년 1월 1일 이후 출생), 군필자는 군복무기간 제외", dict(ME, 출생="2004"), "충족"),
    ("만 24세 이하(2003년 1월 1일 이후 출생), 군필자는 군복무기간 제외", dict(ME, 출생="2003"), "모름"),
    ("타 재단 장학금(학업보조금 포함) 중복 수혜 불가", ME, "충족"), ("타 재단 장학금(학업보조금 포함) 중복 수혜 불가", BLANK, "모름"),
    ("드림장학금 신청자 신청 불가(중복 수혜 불가)", ME, "모름"),
    ("기 교내외 계속 장학생은 지원유형에 따라 추천에서 제외될 수 있음", ME, "충족"), ("기 교내외 계속 장학생은 지원유형에 따라 추천에서 제외될 수 있음", BLANK, "모름"),
    ("대한민국에서 고등학교 졸업(국외 수학은 예외 가능)", dict(ME, 지역={"출신고교": "서울"}), "충족"), ("대한민국에서 고등학교 졸업(국외 수학은 예외 가능)", ME, "모름"),
]
TERM = dict(ME, 학기="2학년 2학기")                     # 끝낸 학기 3 · 지금 학기가 4번째
TERMS = [({"축": "이수학기", "값": {"이하": 4}, "근거": "3학년 1학기(5학기)에 등록 예정인 자"}, "충족"),
         ({"축": "이수학기", "값": {"이하": 3}, "근거": "3학년 1학기(5학기)에 등록 예정인 자"}, "불충족"),
         ({"축": "이수학기", "값": {"이하": 3}, "근거": "3학기 이하 이수자"}, "충족"),
         ({"축": "이수학기", "값": {"이하": 2}, "근거": "2학기 이하 이수자"}, "불충족")]
bad = 0
for cond, want in TERMS:
    got = nf.check(cond, TERM)[0]
    if got != want:
        bad += 1
        print(f"틀림 {cond} → {got} (기대 {want})")
for t, me, want in CASES:
    got = nf.other(t, me)[0]
    if got != want:
        bad += 1
        print(f"틀림 {t[:40]} → {got} (기대 {want})")
st, _ = nf.check({"축": "전공", "값": {"허용": ["전공불문"]}}, ME)
if st != "충족":
    bad += 1
    print("틀림 전공불문", st)
total = len(CASES) + len(TERMS) + 1
print(f"{total - bad}/{total}")
sys.exit(1 if bad else 0)
