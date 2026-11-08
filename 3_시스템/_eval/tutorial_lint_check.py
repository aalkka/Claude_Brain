#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tutorial_lint 회귀 시험 — 통과하는 v2 장 둘(코어·모듈)을 한 줄씩 망가뜨려 규칙마다 막음·경고가 서는지 본다.

  py -3 3_시스템/_eval/tutorial_lint_check.py      실패가 있으면 exit 1

볼트를 건드리지 않는다 — 임시 폴더에 작은 볼트(actions.json · 모듈 하나 · 화면 HTML)를 만들고 지운다.
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]  # 3_시스템/_eval → 3_시스템 · 작업 폴더 사본이면 같은 폴더
import tutorial_lint as T  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

CORE = """---
형식: 2
장: 1
이름: 시험
시간: 1분
없애는 일: 노트를 찾아 헤매기
해낼 일: 연습 노트를 혼자 연다
연습: 연습 노트.md
---
## 열기
말: 이 노트를 눌러 보세요.
보여 주기: 드러내기 @연습 노트.md
가리키기: 탐색기 "연습 노트"
기다리기: 연파일 @연습 노트.md
풀이: open @연습 노트.md here

## 설명
말: 노트는 여기 열립니다.
기다리기: 다음

## 확인
말: 혼자 해 보세요. 노트를 다시 여세요.
보여 주기: close @연습 노트.md
가리키기: 탐색기 "연습 노트"
기다리기: 연파일 @연습 노트.md
풀이: open @연습 노트.md here
"""

MOD = """---
형식: 2
장: 1
이름: 데모
시간: 1분
없애는 일: 출처를 말로 묻기
해낼 일: 후보 출처를 혼자 고른다
연습: 모듈
---
## 열기
말: 이 단추로 화면을 여세요.
가리키기: 리본 "데모"
기다리기: 보임 모듈화면
풀이: 누르기

## 고르기
말: 이 출처를 눌러 보세요.
가리키기: 화면 "출처"
기다리기: 화면 누름 "출처"
풀이: 누르기

## 확인
말: 혼자 해 보세요. 후보를 눌러 보세요.
가리키기: 화면 "후보"
기다리기: 화면 누름 "후보"
풀이: 누르기 화면 "후보"
"""

CHAT_STEP = """
## 묻기
말: 직접 쳐서 보내 보세요.
가리키기: 입력
시킬 말: ^안녕
연습: 답 | 반갑습니다.
기다리기: 늘어남 결과
풀이: 보내기 안녕하세요
"""


def build():
    v = tempfile.mkdtemp(prefix="tt-lint-")
    w = lambda rel, text: (os.makedirs(os.path.dirname(os.path.join(v, rel)), exist_ok=True), open(os.path.join(v, rel), "w", encoding="utf-8", newline="\n").write(text))
    w("3_시스템/actions.json", json.dumps({"actions": [{"id": "files.restore", "name": "되살리기", "risk": "write", "run": ["x"]}]}, ensure_ascii=False))
    mj = {"contributes": {"tutorial": ".claude/skills/demo/tutorial", "view": {"html": ".claude/skills/demo/view/index.html", "practice": ["{py}", ".claude/skills/demo/x.py", "view", "--practice"]},
                          "actions": [{"id": "demo.look", "name": "데모 보기", "risk": "read", "run": ["x"]}, {"id": "demo.ask", "name": "판정", "risk": "usage", "run": ["x"]}]}}
    w(".claude/skills/demo/module.json", json.dumps(mj, ensure_ascii=False))
    w(".claude/skills/demo/view/index.html", '<div data-tt="출처"></div>\n<script>b.dataset.tt = "후보";</script>\n')
    w("3_시스템/views.json", json.dumps({"schema": 1, "views": [{"owner": "demo2", "id": "main", "name": "데모", "html": ".claude/skills/demo/view/index.html", "practice": ["{py}", ".claude/skills/demo/x.py", "view", "--practice"]}]}, ensure_ascii=False))  # 코어 화면(머리 «화면:» 코어 장)
    return v, mj


def main():
    v, mj = build()
    rows, fails = [], 0

    def run(text, module=False, name="1-시험.md"):
        folder = os.path.join(v, ".claude", "skills", "demo", "tutorial") if module else os.path.join(v, "3_시스템", "tutorial")
        os.makedirs(folder, exist_ok=True)
        p = os.path.join(folder, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        r = T.check_chapter(p, "demo" if module else None, mj if module else None, vault=v)
        os.remove(p)
        return r

    def case(label, text, code=None, bucket="blocks", ok=None, module=False):
        """code 가 bucket 에 서야 함 · 경고만 나는 경우는 통과(ok) · code 가 없으면 막음·경고 0"""
        nonlocal fails
        ok = (bucket == "warns" or code is None) if ok is None else ok
        r = run(text, module)
        got = [x["code"] for x in r.get(bucket, [])] if r["chapter"] else []
        good = r["chapter"] and r["ok"] == ok and (code is None or code in got)
        if code is None and r["chapter"]:
            good = good and not r["blocks"] and not r["warns"]
        fails += 0 if good else 1
        rows.append((label, "PASS" if good else "FAIL", "" if good else json.dumps({"ok": r.get("ok"), "blocks": T.lines(r.get("blocks", [])), "warns": T.lines(r.get("warns", []))}, ensure_ascii=False)[:300]))

    rep = lambda a, b, s=CORE: s.replace(a, b, 1)
    # 통과
    case("코어 v2 통과", CORE)
    case("모듈 v2 통과", MOD, module=True)
    case("코어 장 머리 화면: = 코어 화면(views.json · 모듈화면 · 화면 이름 · 연습 모듈)", MOD.replace("장: 1\n", "장: 1\n화면: demo2\n"))
    case("코어 장 머리 화면: + 정리 화면닫기 = 막음 없음(경고 CLEAN 만)", MOD.replace("장: 1\n", "장: 1\n화면: demo2\n정리: 화면닫기\n"), "CLEAN", "warns")
    case("말로 치는 단계 통과", CORE.replace("\n## 확인", CHAT_STEP + "\n## 확인"), ok=True)
    # 머리
    case("형식 없음 = v1", rep("형식: 2\n", ""), "V1")
    case("모르는 형식", rep("형식: 2", "형식: 3"), "HEAD")
    case("해낼 일 없음", rep("해낼 일: 연습 노트를 혼자 연다\n", ""), "T4")
    case("연습 없음", rep("연습: 연습 노트.md\n", ""), "PRAC")
    case("연습 없음+파일", rep("연습: 연습 노트.md", "연습: 없음 · 연습 노트.md"), "PRAC")
    case("연습 파일이 폴더에 없음", rep("연습: 연습 노트.md", "연습: 연습 노트.md · 없는 파일.md"), "PRAC")
    case("선언 안 한 연습", rep("연습: 연습 노트.md", "연습: 없음"), "PRAC")
    case("쓰지 않는 연습", rep("연습: 연습 노트.md", "연습: 연습 노트.md · 연습 자료.pdf"), "PRAC", "warns")
    case("연습 파일 칸", rep("연습: 연습 노트.md", "연습: 연습 노트.md\n연습 파일: 연습 로드맵.md"), "OLD")
    case("정리 칸", rep("연습: 연습 노트.md", "연습: 연습 노트.md\n정리: 창닫기"), "CLEAN", "warns")
    case("모르는 머리 칸", rep("시간: 1분", "시간: 1분\n해낼일: 오타"), "KEY", "warns")
    # 단계
    case("풀이 없음", rep("풀이: open @연습 노트.md here\n", ""), "SOLVE")
    case("빈 기다리기", rep("기다리기: 다음", "기다리기:"), "WAIT")
    case("모르는 기다리기", rep("기다리기: 연파일 @연습 노트.md", "기다리기: 보임하기 홈"), "VOCAB")
    case("다음 뒤 글", rep("기다리기: 다음", "기다리기: 다음 단계"), "VOCAB")
    case("모르는 자리", rep('가리키기: 탐색기 "연습 노트"', '가리키기: 서랍 "연습 노트"'), "VOCAB")
    case("모르는 보여 주기", rep("보여 주기: 드러내기", "보여 주기: 펼치기"), "VOCAB")
    case("확장자 없는 @", rep("보여 주기: 드러내기 @연습 노트.md", "보여 주기: 드러내기 @연습 노트"), "VOCAB")
    case("가리키기 없음", rep('보여 주기: 드러내기 @연습 노트.md\n가리키기: 탐색기 "연습 노트"\n', "보여 주기: 드러내기 @연습 노트.md\n"), "POINT")
    case("자리 낱말", rep("말: 이 노트를 눌러 보세요.", "말: 왼쪽 탐색기의 이 노트를 눌러 보세요."), "T5")
    case("긴 말", rep("말: 노트는 여기 열립니다.", "말: 하나입니다. 둘입니다. 셋입니다. 넷입니다."), "LONG", "warns")
    case("가짜 해 보기", rep("보여 주기: 드러내기 @연습 노트.md", "보여 주기: open @연습 노트.md here"), "FAKE")
    case("세우기만", rep("말: 노트는 여기 열립니다.\n", "말: 노트는 여기 열립니다.\n세우기: 홈\n"), "VOCAB")
    case("모르는 전제", rep("말: 이 노트를 눌러 보세요.", "말: 이 노트를 눌러 보세요.\n전제: 날씨 맑음"), "VOCAB")
    case("모르는 아니면", rep("말: 이 노트를 눌러 보세요.", "말: 이 노트를 눌러 보세요.\n아니면: 몰라"), "VOCAB")
    case("조건 칸", rep("말: 이 노트를 눌러 보세요.", "말: 이 노트를 눌러 보세요.\n조건: 플러그인 brain-calendar"), "OLD")
    case("모르는 행위", rep("풀이: open @연습 노트.md here", "풀이: 행위 없는.행위"), "VOCAB")
    case("말 없음", rep("말: 노트는 여기 열립니다.\n", ""), "SAY")
    # 화면 문(E3 · brain-base 0.43) — 화면 안은 «화면 <사건>» 기다리기와 누르기·치기만
    case("화면 안 상태는 «화면 보임» 꼴만", MOD.replace('기다리기: 화면 누름 "출처"', '기다리기: 보임 화면 "출처"'), "VOCAB", module=True)
    case("화면 안 고르기 없음", MOD.replace('풀이: 누르기 화면 "후보"', '풀이: 고르기 화면 "후보"'), "VOCAB", module=True)
    case("화면 바뀜·보임 · 치기 = 통과", MOD.replace('기다리기: 화면 누름 "출처"\n풀이: 누르기', '기다리기: 화면 바뀜 "출처"\n풀이: 치기 화면 "출처" 낱말').replace('기다리기: 화면 누름 "후보"', '기다리기: 화면 보임 "후보"'), module=True)
    # 보낼 말
    put_step = CHAT_STEP.replace("시킬 말: ^안녕", "넣기: 안녕").replace("풀이: 보내기 안녕하세요\n", "")
    case("넣기 = 경고", rep("\n## 설명\n말: 노트는 여기 열립니다.\n기다리기: 다음\n", put_step), "PUT", "warns")
    case("넣기 = 해 보기로 안 셈", CORE.replace("\n## 확인", put_step + "\n## 확인"), "T1")
    case("넣기와 시킬 말", CORE.replace("\n## 확인", CHAT_STEP.replace("시킬 말: ^안녕", "시킬 말: ^안녕\n넣기: 안녕") + "\n## 확인"), "CHAT")
    case("연습 답 없는 시킬 말", CORE.replace("\n## 확인", CHAT_STEP.replace("연습: 답 | 반갑습니다.\n", "") + "\n## 확인"), "CHAT")
    case("정규식 꼴", CORE.replace("\n## 확인", CHAT_STEP.replace("^안녕", "(안녕") + "\n## 확인"), "CHAT")
    case("풀이 말이 안 맞음", CORE.replace("\n## 확인", CHAT_STEP.replace("보내기 안녕하세요", "보내기 잘 가") + "\n## 확인"), "SOLVE")
    case("보낼 말 없는 연습 답", rep("말: 노트는 여기 열립니다.", "말: 노트는 여기 열립니다.\n연습: 답 | 글"), "CHAT")
    case("보낼 말 없이 결과 기다림", rep("기다리기: 연파일 @연습 노트.md\n풀이: open @연습 노트.md here\n\n## 설명", "기다리기: 늘어남 결과\n풀이: 누르기\n\n## 설명"), "CHAT")
    # 장 전체
    case("해 보기 아닌 단계 연달아", rep("## 확인", "## 설명 둘\n말: 하나 더.\n기다리기: 다음\n\n## 확인"), "T1")
    case("첫 단계가 글", rep("## 열기", "## 머리말\n말: 시작합니다.\n기다리기: 다음\n\n## 열기"), "T1")
    case("확인 없음", rep("## 확인", "## 다시"), "T4")
    case("확인이 끝이 아님", rep("## 설명", "## 확인 먼저\n말: 혼자 여세요.\n가리키기: 탐색기 \"연습 노트\"\n기다리기: 연파일 @연습 노트.md\n풀이: open @연습 노트.md here\n\n## 설명"), "T4")
    case("긴 장", CORE.replace("\n## 확인", "".join(f"\n## 열기{i}\n말: 여세요.\n가리키기: 탐색기 \"연습 노트\"\n기다리기: 연파일 @연습 노트.md\n풀이: open @연습 노트.md here\n" for i in range(6)) + "\n## 확인"), "LEN", "warns")
    # 모듈
    case("코어가 모듈 화면", rep('가리키기: 탐색기 "연습 노트"', '가리키기: 화면 "출처"'), "VOCAB")
    case("없는 data-tt", MOD.replace('가리키기: 화면 "출처"', '가리키기: 화면 "없는 이름"'), "VOCAB", module=True)
    case("코어 장 머리 화면: 없는 owner", MOD.replace("장: 1\n", "장: 1\n화면: 없는것\n"), "HEAD")
    case("코어 장이 머리 화면: 없이 모듈 화면을 가리킴", MOD, "VOCAB")
    case("화면 안인데 연습 모듈 없음", MOD.replace("연습: 모듈", "연습: 없음"), "PRAC", module=True)
    # 연습 화면(E2) — «연습: 모듈» 은 그 화면 선언에 연습 자료 명령(practice)이 있어야 함(모듈 · 코어)
    keep = mj["contributes"]["view"].pop("practice")
    case("연습 모듈인데 모듈 화면에 practice 없음", MOD, "PRAC", module=True)
    mj["contributes"]["view"]["practice"] = keep
    vj = os.path.join(v, "3_시스템", "views.json")
    with open(vj, encoding="utf-8") as f:
        vj_text = f.read()
    with open(vj, "w", encoding="utf-8", newline="\n") as f:
        f.write(vj_text.replace(', "practice": ' + json.dumps(keep, ensure_ascii=False), ""))
    case("연습 모듈인데 코어 화면(views.json)에 practice 없음", MOD.replace("장: 1\n", "장: 1\n화면: demo2\n"), "PRAC")
    with open(vj, "w", encoding="utf-8", newline="\n") as f:
        f.write(vj_text)
    case("화면 사건 꼴", MOD.replace('기다리기: 화면 누름 "출처"', '기다리기: 화면 클릭 "출처"'), "VOCAB", module=True)
    case("진짜 먼저(T6)", MOD.replace("\n## 확인", CHAT_STEP + "\n## 확인"), "T6", "warns", module=True)
    case("진짜 행위를 쓰면 T6 없음", MOD.replace("\n## 확인", CHAT_STEP + "\n## 보기\n말: 골라 보세요.\n보여 주기: 홈\n가리키기: 홈 \"행위 고르기\"\n기다리기: 보임 창 \"✓ 데모 보기\"\n풀이: 행위 demo.look\n" + "\n## 확인"), ok=True, module=True)
    # v1 · 대본 아님 · 폴더
    r = run("---\n장: 1\n이름: 시험\n연습 파일: 없음.md\n---\n## 하나\n기다리기: 다음\n")
    good = r["version"] == 1 and not r["ok"] and "단계 «하나» 에 «말:» 없음." in r["legacy"] and "연습 파일 없음 '없음.md'(대본 폴더 안)." in r["legacy"]
    fails += 0 if good else 1
    rows.append(("v1 = 지금 엔진 꼴(⑫ 와 같은 말)", "PASS" if good else "FAIL", "" if good else json.dumps(r["legacy"], ensure_ascii=False)))
    r = run("---\ntitle: 연습\n---\n# 연습 지도\n- 상태: 끝\n")
    fails += 0 if r["chapter"] is False else 1
    rows.append(("장 번호 없는 md = 대본 아님", "PASS" if r["chapter"] is False else "FAIL", ""))
    d = os.path.join(v, "3_시스템", "tutorial")
    for nm in ("1-가.md", "1-나.md"):
        with open(os.path.join(d, nm), "w", encoding="utf-8") as f:
            f.write(CORE)
    g = T.check_folder(d, vault=v)
    good = len(g["chapters"]) == 2 and any("장 번호 1 겹침" in x for x in g["problems"])
    fails += 0 if good else 1
    rows.append(("폴더 — 장 번호 겹침", "PASS" if good else "FAIL", "" if good else json.dumps(g["problems"], ensure_ascii=False)))

    shutil.rmtree(v, ignore_errors=True)
    for label, res, detail in rows:
        print(f"{res}  {label}" + (f"\n      ↳ {detail}" if detail else ""))
    print(f"{len(rows) - fails}/{len(rows)} PASS" + ("" if not fails else f"  ({fails} FAIL)"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
