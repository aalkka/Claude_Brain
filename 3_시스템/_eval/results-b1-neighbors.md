---
type: decision
title: Phase 3.5 B1 — 의미이웃 임계 재보정 (절대임계 폐기 → per-node top-k 상대방식)
created: 2026-07-04
updated: 2026-07-04
tags: [외부뇌, eval, phase3.5, b1, neighbors, graph, decision]
status: active
source: session
---
# B1 결정: 절대 cosine 임계 폐기 → per-node top-k 상대방식

> ※ **빌드 당시 측정 기록.** 페이스밸리디티 예시로 언급되는 논문노트(MemGPT·LLMLingua 등)는 배포 스트립으로 삭제됨(git 이력 보존). 방법·수치·결론은 그대로 유효.

## 블로커 (인계 경고 실측 확증)
e5-small 임베딩 **이방성**(anisotropy) → 전 노트쌍 max-chunk-cos가 좁은 원뿔에 압착:
| N=1326쌍 | min | p25 | median | p75 | p90 | p99 | max |
|---|---|---|---|---|---|---|---|
| max-chunk-cos | **0.802** | 0.857 | 0.880 | 0.916 | 0.935 | 0.965 | 1.000 |
- **절대임계 무용:** thr 0.60/0.75/0.80 전부 **완전그래프**(1326엣지=모든 노드가 51개 전부와 연결, 헤어볼). 0.90서도 avg차수 18.7. 원 코드 `thr=0.6` = 전노트 연결.
- top1 이웃 cos: min 0.919·median 0.965 → **최근접조차 절대값으론 나머지와 구분 불가.** 절대 스칼라 임계는 이 분포서 원리적으로 작동 못 함.

## 방법 비교 (정답신호 = 볼트 수동 위키링크 57엣지)
labeled neighbor 골든 없음 → **기존 수동 [[링크]] 57엣지를 인간판정 정답**으로 사용. recall=의미방법이 수동링크 회복률. precision은 느슨 해석(B1 임무=비자명 엣지 **추가**라 신규엣지는 정상; 수동링크 다수는 MOC 허브링크=구조적).

| 방법 | E | avg차수 | 고립 | 성분 | recall | 판정 |
|---|---|---|---|---|---|---|
| 절대 thr=0.88 | 661 | 25.4 | 0 | 1 | 100% | **헤어볼**(prec 8.6%) ✗ |
| 상호kNN k=3 | 38 | 1.5 | 11 | 24 | 25% | **파편화**(교과서 이방성해법인데 소규모서 고립양산) ✗ |
| 센터링 top-k k=3 | 106 | 4.1 | 0 | 2 | 46% | 이방성보정이 recall 개선 0 → 복잡도만 ✗ |
| **top-k union k=3** | **118** | **4.5** | **0** | **2** | **49~51%** | **채택** ✓ |
| top-k union k=5 | 187 | 7.2 | 0 | 2 | 56% | k=3 대비 밀도↑ (옵션) |

**top-k union k=3 = 가독성 프론티어 지배**: 고립0, 성분2(=진짜 토픽섬: 지식/세션/메모리 vs 설계노트/pdf), 희소군 최고 precision.

### max-pool vs mean-pool(centroid)
neighbors는 "노트전체 유사도"라 mean-pool이 이론상 나을 수 있어 측정:
| pool | k=3 recall | 제작가이드 허브차수 | 스팟체크 |
|---|---|---|---|
| max-chunk | 51% | 14 | paper→paper 깔끔 |
| mean(centroid) | 49% | 15 | 교차클러스터 다소 노이즈 |
→ **max-pool 유지**: recall 동등이상, 허브차수 동일(즉 제작가이드 허브성은 max-pool 아티팩트 아니라 **진짜**—마스터 빌드문서가 하위 설계노트 내용 포함), 검색경로와 코드 일관(신규경로 0). 오컴.

## 최종 방법 (search.py `neighbors()`)
**per-node top-k(k=3) raw max-chunk-cos + 중복드롭 + 상대floor. 절대임계 삭제.**
1. `NEIGH_K=3` — 노드당 이웃 상한. union 렌더 시 avg차수 4.5.
2. `NEIGH_DUP=0.999` — cos≥이면 색인중복(변환본↔pdf-cache 동일본) → 이웃서 제외. 제작가이드 허브차수 14→12로 정화. **임시 가드**(Phase5 dedup 시 근본해소).
3. `NEIGH_FLOOR=0.08` — 자기 top1 대비 상대 하한. **k=3서 현재 무효과**(원뿔 조밀, top-3가 항상 top1 근처) → 미래 아웃라이어/큰 k용 안전레일.

## 페이스밸리디티 (라이브)
- MemGPT → Context-Engineering·LLMLingua·Generative-Agents (전부 에이전트메모리/컨텍스트 논문) ✓
- LLMLingua → LongLLMLingua(속편)·TRIM·CoALA (압축 논문) ✓✓
- 벡터검색_설계 → 정합패스_개정·MVP범위·전체구조 (설계 클러스터) ✓
- incident-cp949 → incident-스펙실측괴리(다른 인시던트)·Phase1-4세션 ✓

## 한계·미결
- 정답신호(수동링크 57)도 자작·소규모. recall 49%는 **허브링크(MOC→전부) 제외 시 실질 의미이웃 대부분 회복**이 실체(precision 낮음=신규엣지 다수=B1 기능).
- **색인중복**(변환본/pdf-cache 동명 11쌍, cos 1.0): dup-drop이 자기쌍은 억제하나 "이웃의 쌍"(동명 2회 등장)은 잔존 → **writer가 basename dedup**으로 흡수. 근본해소=Phase5 스코프정리.
- 코퍼스 52노트. 규모↑ 시 k 재검토(union 밀도 선형↑).

## B1 writer (완료 2026-07-04, 디자인 개정)
`search.py --link-dryrun`(미리보기) / `--link-write`(실기입). Claude소유 지식노트 12개에 관리블록 기입.
- **블록 디자인**(v3, 건희 검토·현행): **접이식 콜아웃**(`[!info]-` 기본 접힘) + 마커 `%%sl%%`를
  **제목줄 인라인** 삽입. 독립 주석줄 0 → reading·**편집(Live Preview)** 양쪽서 마커 안 보임(콜아웃만 렌더).
  위키링크는 콜아웃 본문(그래프 인덱싱 유지).
  ```
  > [!info]- 관련 노트 %%sl%%
  > [[A]] · [[B]] · [[C]]
  ```
  - v2(`%% sl %%` 독립 주석줄) 폐기 사유: **편집모드서 독립 주석줄 노출**(건희 지적). v1=`<!-- -->`+볼드줄.
- `_BLOCK_ALT` 정규식이 v1·v2·v3 3세대 매치 → 마이그레이션 시 구→신 무중복 교체(독립주석줄·구마커 0잔존 실측).
- 스코프 `WRITER_GLOBS` = 2_지식/notes·sessions·3_시스템/_ref. **1_수집·설계노트 제외**(사용자저작/Phase5).
- 링크대상 제외 `LINK_TARGET_EXCLUDE` = pdf-cache·_변환본(기계파생 중복 → 그래프 오염 방지). basename dedup.
- **idempotent**: 마커로 기존블록 교체(재실행 0 변경 실측). block=None→제거.
- ⚠ **피드백루프 가드**: 관리블록은 파생데이터 → `strip_managed()`가 색인(임베딩+lexical) 유입 차단.
  미차단 시 "노트가 이웃이름 포함→재색인→그 이웃과 유사도↑" 자기강화. reindex 후 이웃 불변 실측(MemGPT 0.930/0.925/0.925 동일).
- k(이웃밀도)·dup·floor = **config.json "graph" 블록 소프트코딩**(setup-interview 슬롯으로 변경). 기본 k=3.


## 상태
**B1 채택**(임계재보정+writer, 네이티브 그래프뷰로 목적달성). Phase 3.5 종료.
다음=Phase 4.5(README·tag·setup-interview 슬롯에 graph.neigh_k 편입)→Phase 5.
