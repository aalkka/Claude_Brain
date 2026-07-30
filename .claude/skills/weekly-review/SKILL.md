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
7. **코어 게이트 계측**(→ `_ref/코어수정-준수사항-체크리스트.md`). 읽기 전용으로 실행 → 보고:
   - `git log --since="7 days ago" --oneline -- "3_시스템/hooks/" "3_시스템/search.py" CLAUDE.md "3_시스템/conventions.md" .claude/settings.json` → **코어 변경 커밋 수**, 그중 메시지가 `session:`인 것(=절차 흔적 없는 익명 수정) 수를 함께.
   - `3_시스템/_index/core-gate.log` 줄 수 → **게이트 발동 횟수**.
   - 판정: 발동 0인데 코어 변경이 있으면 **게이트가 죽었거나 우회됐다**(교차검증 — 두 수의 불일치가 유일한 생존 신호). 익명 커밋이 있으면 해당 해시를 나열해 사후 검토 대상으로 보고. **고치지 말고 보고만** 한다.
   - **frontmatter YAML 위반 건수**(§10 임계 측정값):
     `find 2_지식 3_시스템/_ref -name '*.md' -type f | while read f; do awk 'NR==1&&$0!="---"{exit} NR>1{if($0=="---")exit; if(match($0,/^[A-Za-z_][A-Za-z0-9_]*:[ \t]*/)){v=substr($0,RLENGTH+1); if(v~/^"/){if(v!~/^"[^"]*"[ \t]*$/)bad=1} else if(v!~/^[["{]/&&v~/:[ \t]/)bad=1}} END{exit bad?1:0}' "$f" || echo "$f"; done`
     → 출력된 파일이 **누적 2건 이상이면** 프론트매터 실파싱 검사 도입을 제안(적용은 사용자 승인 후 — 코어 수정).
