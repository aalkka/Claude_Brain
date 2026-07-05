---
type: decision
title: Phase 3 검색 노선 결정 — 하이브리드(lexical+vector) 채택
created: 2026-07-03
updated: 2026-07-03
tags: [외부뇌, eval, phase3, hybrid, decision]
status: active
source: session
---
# Phase 3 결정: 하이브리드 검색 채택 (grep-단독/벡터-단독 기각)

> ※ **빌드 당시 측정 기록.** 본문이 언급하는 논문노트(MemGPT·LLMLingua 등)·`results-baseline`·`_변환본`은 배포 스트립으로 삭제됨(git 이력 보존). 수치·결론은 그대로 유효.

## 배경 — 노선 변경 이력
1. Phase 2 grep 베이스라인 = hit@8 **100%** → 규약 사다리대로면 "벡터 불필요, grep 래퍼" 결론(results-baseline — 삭제·배포 제외).
2. 건희님 기각: 100%는 **골든셋이 literal 기술어(MemGPT·LLMLingua 등)로 작성돼 grep 홈그라운드만 측정**한 산물. 실 외부뇌 질의 = 사용자 지식·경험을 **두루뭉술한 소수 키워드**로 찾음 → grep 취약, 의미검색 필요. **단 grep 정밀도는 버리지 말 것 → 하이브리드.**
3. 측정으로 검증(측정 전 아키텍처 금지 준수).

## 측정 (search.py: 청킹 max-pool + recency off + RRF k60 하이브리드)
3자 = lexical(grep형 토큰빈도) · vector(max-chunk cosine) · hybrid(RRF k=60).

### 최종 (2026-07-04, 전 골든 PDF 8편 인제스트 후 — 43노트)
| 골든셋 | lexical | vector | **hybrid** |
|---|---|---|---|
| literal 30 | 30/30 | 30/30 | **30/30 (100%)** |
| 패러프레이즈 12 | 11/12 | 10/12 | **12/12 (100%)** |
→ **완전 Pareto: hybrid ≥ max(arm) 양쪽, 패러프레이즈선 각 arm(11·10) 초월.** literal=grep 동률(비효율 소멸), 패러프레이즈=하이브리드 고유가치 실증(각 arm이 놓친 걸 융합이 전부 회복). 융합 코드 무변경 — 원인은 영어 스캐폴드, 레버는 인제스트.

### 진행 이력 (스캐폴드→인제스트 효과)
| 시점 | literal hybrid | 패러프레이즈 hybrid |
|---|---|---|
| 청킹 전(통짜, recency0.2) | — | vec 50% |
| 청킹+RRF, 인제스트 0 | 90.0% | 58.3% |
| PDF 2편 인제스트 | 96.7% | 66.7% |
| PDF 8편 전량 인제스트 | **100%** | **100%** |
(참고: 수동 grep 단일키워드도 literal 100%. 절대치 100%는 코퍼스 소규모+자작 골든 편향 포함 — 상대 비교[hybrid>arm]가 신호.)

## Phase 4 재측정 (PDF 1편 인제스트 후 — 교차언어 가설 확증)
MemGPT PDF(영어) → 한국어 통찰노트(`2_지식/notes/MemGPT.md`) 인제스트 + golden의 MemGPT 답 교체:
| 골든셋 | 인제스트 전 hybrid | 인제스트 후 hybrid |
|---|---|---|
| literal 30 | 90.0% | 93.3% |
| 패러프레이즈 12 | 58.3% | **66.7%(8/12)** |
- MemGPT 패러프레이즈 질의: 영어 _변환본서 **rank20(전모드 miss)** → 한국어 통찰노트 **rank1**.
- **확증:** PDF 패러프레이즈 실패는 교차언어(영어원문)였지 모델용량 아님. 한국어 인제스트가 해결 → **bge-m3 불요 재확인.** 나머지 4 PDF도 인제스트 시 유사 회복 예상(패러프레이즈→~12/12 수렴 가설, Phase 5 전량 인제스트 후 확인).

## 융합 비효율 조사 (2026-07-04, 건희님 지적: literal서 hybrid<lexical)
지적: grep/lexical=literal 29/30인데 hybrid 28 → 융합이 강한 arm 희석 = 비효율?
**진단:** literal서 hybrid가 지는 질의 = **딱 1개(context_managing1)**. 랭크 L=5(hit)·V=20(쓰레기)·H=13(miss). 약한 vector가 강한 lexical을 문턱 밖으로 끌어냄.
**융합 변형 실측(추측 금지):**
| 융합 | literal | 패러프레이즈 | 합 |
|---|---|---|---|
| RRF k60(현행) | 28 | **8** | 36 |
| wRRF 2:1 / 3:1 | 29 | 7 | 36 |
| convex α0.5~0.7 | 28~29 | 7 | 36 |
→ **literal 1개 회복 = 패러프레이즈 1개 상실. 전 변형 36/42 동률.** 순수 융합튜닝으론 trade-off 못 깸. 문헌도 convex 튜닝 "표본효율 낮고 도메인시프트 취약"(과적합) 경고 → 42문 자작셋 튜닝은 부적절.
**진짜 원인·해결:** 손실 질의(context_managing1)=영어 미인제스트 스캐폴드. 인제스트(→한국어 통찰노트)만으로 융합 무변경인데 **literal hybrid 28→29(=lexical, Pareto 충족), 패러프레이즈 8 유지.** MemGPT·context1 두 선례로 실증. → **"융합 비효율"은 오진, 스캐폴드 아티팩트가 원인.** 융합=RRF k60 유지(변경 불요).
**최종 상태:** hybrid ≥ max(arm) — literal 29(=lexical)·패러프레이즈 8(>7). 이상적 Pareto.
출처: [RRF vs 점수기반/convex](https://medium.com/mongodb/reciprocal-rank-fusion-and-relative-score-fusion-classic-hybrid-search-techniques-3bf91008b81d) · [Weighted RRF](https://medium.com/@shubhamsarkar996/hybrid-search-in-rag-concept-of-weighted-reciprocal-rank-fusion-rrf-part-1-ae570d9c1879) · [Assembled: RRF for RAG](https://www.assembled.com/blog/better-rag-results-with-reciprocal-rank-fusion-and-hybrid-search)

## 핵심 증거 (건희님 주장 검증)
- **상보성 실증:** 패러프레이즈서 lexical·vector가 **서로 다른 6문**을 맞힘 → RRF 합집합 = 7문. 융합이 각 arm 단독을 능가(**58.3 > 50**). = 하이브리드의 존재 이유.
- **미스 분해(패러프레이즈, hybrid):** 한국어 대상(설계노트·세션·incident) **7/7 성공**, 영어 PDF(_변환본) **0/5 실패**. → 한국어→한국어 의미질의선 하이브리드 사실상 완벽. 실패는 전부 **교차언어(한국어 질의 vs 영어 원문)**.
- literal서 hybrid(90) < lexical(93)인 건 **한 arm 지배 구간선 RRF가 소폭 손해**(정상). 실사용은 패러프레이즈 우세 → 두 구간 합산 커버가 하이브리드.

## ⚠ 증거 취약성 (2026-07-03 비판점검 — 채택은 잠정)
정밀 분해(패러프레이즈 12문, 컬럼 L/V/H):
- **PDF 5문(영어 원문 _변환본) = 전 모드 몰살 0/5.** 진짜 의미검색이 필요한 지점서 벡터가 정확히 실패(교차언어).
- **벡터 고유 기여 = 문제해결_검증 1문뿐**(어휘 고유 = 정합패스 1문). hybrid 7 vs 각 arm 6의 실체 = 서로 다른 1문씩 구제. **"벡터가 의미로 값어치" 증거 = 실질 1문**, 자작·n=12.
- 성공한 한국어 패러프레이즈도 소스 어휘 근접 → 얕은 겹침 가능성(깊은 의미 미검증).
- **측정 대상 = search.py 내부 하이브리드(기계적)**, 실제 skill(Grep도구+Claude 재랭킹) 아님. baseline 100%(에이전틱)와 직접비교 불가.

→ ~~하이브리드 채택 = 잠정~~ → **문헌 검증 후 확정(아래).**

## 문헌 검증 (2026-07-04 — IR 합의가 소규모 측정 보강)
n=12 자작셋의 통계력 부족을 대규모 IR 벤치마크가 대체. 우리 측정 패턴이 정설과 일치:
- **상보성:** dense(벡터)=의미·패러프레이즈·동의어·교차언어 우세 / BM25(grep형)=고유명사·기술코드·희귀어 우세. "각자 놓친 걸 상대가 찾음." → 우리 per-query(정합패스=lexical만, 문제해결=vector만)와 동형.
- **hybrid > max(각 arm):** BEIR "거의 모든 경우" 성립(nDCG 43.4→52.6). → 우리 hybrid ≥ 각 arm 재현.
- **vocabulary mismatch = dense 존재이유.** 건희님 "지식은 두루뭉술 키워드라 grep 어려움" = 이 문제 그대로.
- ⚠ **경고(BEIR 2021):** 약한 dense(MS MARCO·zero-shot 교차도메인)는 BM25 못 이김 — pooling이 정확문자열·희귀어 어휘정체성 파괴. **우리 e5-small(작음·미파인튜닝·한국어)이 이 케이스** → 벡터 arm 50~58%는 **바닥이지 천장 아님.**

**결정: 하이브리드 확정**(문헌+측정+메커니즘 3중 근거). 남은 미결 = "hybrid냐"(해결) 아니라 "dense arm 품질 어디까지".

### dense 품질 레버 (ROI순, 측정 실증 시 복원)
1. **reranker(cross-encoder)** — 문헌이 최대 품질레버로 강조. 벡터검색_설계 D6(`bge-reranker-v2-m3`). hybrid top-N 재정렬.
2. **bge-m3** — 강한 dense. 단 교차언어 갭은 한국어 인제스트가 더 쌈(실증). 코퍼스 성장+reranker로도 부족 시.
3. 도메인 파인튜닝 — 최후.

출처: [IEEE Lexical/Dense/Hybrid RAG](https://ieeexplore.ieee.org/document/11379254/) · [BM25 still wins on queries that matter](https://tianpan.co/blog/2026-04-12-hybrid-search-production-bm25-dense-embeddings) · [Hybrid BM25+Dense fusion](https://mbrenndoerfer.com/writing/hybrid-search-bm25-dense-retrieval-fusion) · [Sparse vs Dense for RAG](https://mljourney.com/sparse-vs-dense-retrieval-for-rag-bm25-embeddings-and-hybrid-search/)

## Phase 4 재측정 (PDF 1편 인제스트 후 — 교차언어 가설 확증)

## 결정 (확정 — 문헌+측정+메커니즘 3중)
1. **search.py = 하이브리드 RRF (확정 채택).** lexical arm(토큰빈도) + vector arm(청킹 max-pool cosine). recency 가중 = **0**(지식검색서 역효과 실측: 66.7→70→73.3% as 0.2→0.1→0).
2. **청킹 채택:** 헤딩 단위 + 긴 섹션 창(40줄), 노트 스코어=max-chunk. 통짜 임베딩 희석 해결(벡터 73.3→83.3%).
3. **bge-m3 = 빌더에겐 DEFERRED, 배포판엔 1급 티어 옵션(폐기 아님).** ⚠ 두 개념 분리:
   - **빌더(건희님 RTX3060 6GB) 측정경로:** e5-small 하이브리드로 측정 충분 → 상향 불요. 잔여 실패=영어 PDF 교차언어인데 **Phase 4 인제스트(영어PDF→한국어 통찰노트)가 더 싸게 해결**(질의도 한국어). 모델용량 병목 미실증.
   - **배포 사용자(제각각 하드웨어):** bge-m3는 **상시 지원 티어**. setup-interview 슬롯8이 하드웨어 감지→티어 자동선택.

### 모델 티어 전환 절차 (배포판 — 잘 꺼내 쓸 것)
코드 = 모델·차원 불가지. **config.json 한 줄 + 전체 재빌드**로 전환. 코드 수정 0.

| 티어 | 조건(설치 PC) | embed_model | 차원 |
|---|---|---|---|
| 고 | CUDA GPU ≥8GB VRAM | `BAAI/bge-m3` | 1024 |
| 중 | GPU 4~8GB / 강CPU | `intfloat/multilingual-e5-base` | 768 |
| 저(기본) | CPU-only | `intfloat/multilingual-e5-small` | 384 |

1. `3_시스템/config.json`의 `"embed_model"` 교체.
2. (고티어) CUDA torch: `py -3 -m pip install torch --index-url https://download.pytorch.org/whl/cu121`.
3. `py -3 3_시스템/search.py --rebuild` (차원 달라 필수). **안전장치:** 인덱스에 `_model` 각인 → config 모델 ≠ 인덱스 모델이면 `--reindex`도 자동 전체 재빌드(차원혼합 오류 차단, 코드 구현됨).
4. e5 계열=프리픽스 `query:`/`passage:` 자동, bge 계열=프리픽스 생략(`is_bge`, 구현됨).

**bge-m3 복원조건(빌더 경로):** Phase4 인제스트 후에도 한국어 통찰노트 패러프레이즈서 벡터 arm 실패 다발 시. (배포는 조건 무관 — 하드웨어가 조건.)

## 정직한 한계
- 패러프레이즈 절대치 58% 낮음 — 영어 _변환본(미인제스트 스캐폴드) 탓. **Phase 4 후 재측정 필수**(한국어 통찰노트로 PDF 대상 교체).
- 코퍼스 34노트(top-8=코퍼스 24%) — 규모↑ 시 재측정.
- 패러프레이즈 골든도 자작(순환성 잔존, 단 이번엔 의미축 시험이라 literal 편향과는 다른 축).
- lexical arm(python 토큰빈도)이 수동 grep보다 약함(93 vs 100) — search 스킬은 실제 Grep tool 병용 권장.

## 규약 반영
- results-baseline(삭제·배포 제외): "grep 래퍼·벡터 N/A" 결론 = **본 문서로 상위 교체**(SUPERSEDED).
- [measure.md](measure.md): 패러프레이즈 골든 + 3자 측정을 상시 회귀에 추가.
- 스킬 `search`(SKILL.md): grep(정밀) + search.py 하이브리드 병합 명시.
- 가이드 Phase 3 분기표: literal-only 측정의 한계 + 하이브리드 채택 각주.
