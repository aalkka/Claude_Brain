---
name: weekly-review
description: 주간 점검. 사용자가 주 1회 호출.
---
1. 지난주 sessions/ 훑기(제목+gist만) → 통찰노트 1개 작성(type:semantic, confidence:hypothesized, 소스 링크).
2. inbox-sort 실행.
3. `2_지식/open-loops.md`: **이중 주체 정리** — ①사용자가 `- [x]` 체크한 항목 삭제 ②Claude가 종결로 판단한 항목도 삭제. 판단이 애매한 스테일 항목은 지우지 말고 **체크 후보로 나열해 보고**. 아울러 **형식 위반 건수 보고** — `## ` 섹션 아래 최상위 `- ` 줄인데 `- [ ]`/`- [x]` 가 아닌 것(설계노트 §10 훅 복원조건의 측정값).
4. **골든셋 있으면** 5문 샘플 재측정(`py -3 3_시스템/search.py --eval <골든>`) → `_eval/results-weekly.md` 추가, 낙폭 시 보고. **없으면**(배포 초기 — 사용자 미작성) `_eval/measure.md` 절차로 골든 작성 권유 후 이 스텝 스킵.
5. _ref 신규 incident 있으면 MOC 반영.
6. 헬스: 인덱스·백업·노트 수 보고. `_index` 총용량 + `_index/work/` 잔여 개수 함께 보고. **삭제하지 않는다** — 설계노트 §10 임계(`_index`>200MB 또는 `work/`>50개) 초과 시에만 사용자에게 정리를 제안.
