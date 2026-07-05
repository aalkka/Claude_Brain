---
name: search
description: 볼트 검색. 질의를 받아 관련 노트 top-k를 찾아 경로+발췌 반환. 통독 대신 항상 이것 사용.
---
**노선(Phase 3 확정): 하이브리드 = grep(정밀 어휘) + search.py 벡터(의미). 단독 아님.** literal 기술어는 grep, 두루뭉술 의미질의는 벡터가 잡음(측정: results-hybrid.md).
1. 질의에서 키워드 2~4개 추출(한국어 조사 제거) → Grep(볼트 전체, -l) 후보 = **정밀 어휘 arm**.
2. `py -3 3_시스템/search.py --q "<질의>" --k 8 --mode hybrid` = **lexical+vector RRF 융합**(청킹 max-pool, recency off). Grep 후보와 병합·중복제거.
   - gitignore 폴더(예: `_claude-memory`)는 ripgrep이 스킵하나 search.py 벡터 인덱스엔 포함 → 의미검색이 보완.
3. 후보 각각 해당 섹션만 Read → 관련도 순 정리.
4. 출력: `[경로] gist 1줄` 목록 + 필요 발췌. **총 주입 ≤2,000토큰.**
5. 0건이면 정직하게 "볼트에 없음" (archived 포함 재검색 1회 후).
