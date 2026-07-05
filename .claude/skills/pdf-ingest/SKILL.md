---
name: pdf-ingest
description: PDF를 볼트 지식으로. PDF 읽기 요청 시 통독 대신 이것.
---
**원칙(건희님 확정 2026-07-04): pdf-ingest는 문서를 생략·축약·삭제하지 않는다.** 전문을 마크다운으로 변환·정제(노이즈만)·**청킹 인덱싱**해서 "원하는 부분만" 검색·읽게 하는 것이 목적. 통찰노트는 **gist 포인터**일 뿐 원문 대체 아님(§2).

1. `py -3 -m markitdown <pdf> -o 3_시스템/_index/pdf-cache/<name>.md` (hash 동일하면 스킵). = **전문 정제본**(검색 대상, TARGET_GLOBS 포함).
2. **정제(보수적 — 내용 삭제 금지):** 명백한 노이즈만 제거(깨진 테이블 잔여·중복 헤더·페이지번호 아티팩트). **본문 문단·데이터·표 내용은 보존.** 애매하면 남긴다. References는 남겨도 무방(검색 노이즈 낮음).
3. **통찰노트(gist 포인터)** → `2_지식/notes/<논문명>.md`: 초록+결론+핵심주장 **요지**(짧게) + **원문 정제본 경로 포인터** + frontmatter(type:semantic, source:pdf, **confidence:hypothesized**, importance 6, links). MOC 등록. → 개요질의용. **원문 대체 금지 — 디테일은 전문 인덱스가 담당.**
4. **전문 정제본 인덱싱(필수):** `py -3 3_시스템/search.py --reindex` → pdf-cache 전문이 청킹·인덱싱됨. (개요=통찰노트, 디테일=전문 청크가 검색에 잡힘.)
5. 이후 이 PDF 질문 = search 경유. **원문 필요 시 정제본(pdf-cache/<name>.md)의 해당 섹션만 Read**(전문 보존됨).

주의: pdf-cache는 gitignore(_index) = 로컬·재생성(PDF서). 인덱스 커버는 되나 git 백업은 원본 PDF 보관으로 대체(재인제스트 가능).
