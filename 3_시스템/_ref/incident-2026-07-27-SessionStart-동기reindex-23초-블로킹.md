---
type: incident
title: SessionStart 훅 23초 블로킹 — 동기 reindex의 모델로드
created: 2026-07-27
status: resolved
tags: [incident, 훅, 성능, reindex, 임베딩]
---
# SessionStart 훅 23초 블로킹

## 증상
매 세션 시작·재개마다 체감 지연. `/doctor` 트랜스크립트 집계(48세션·25.9일, 81회 실행)로 실측:

| 이벤트 | 실행 | 중앙값 | p90 | 최대 |
|---|---|---|---|---|
| SessionStart:resume | 39 | **28,991ms** | 83,722ms | 104,841ms |
| SessionStart:startup | 42 | **22,983ms** | 59,225ms | 118,433ms |

임계는 SessionStart 계열 >10s. 타임아웃 기록은 0 — 훅이 죽은 게 아니라 **사용자가 그만큼 기다린** 것.

## 근본원인
`session-start.ps1`의 `py -3 search.py --reindex` **동기 실행**. 구간별 실측:

| 구간 | 실측 |
|---|---|
| 모델 로드(HF Hub 확인 포함) | 15.6s |
| └ 그중 HF Hub 네트워크 확인 | 5.1s (`HF_HUB_OFFLINE=1` 시 10.5s) |
| reindex 나머지(해시·인코딩·저장) | ~2.8s |
| git push RTT | ~1.5s |
| 노트 카운트 | 0.1s |
| **합계** | **~20s** (실측 중앙값 23s와 부합) |

**지연로드는 이미 정상 작동한다**(`search.py:218`·`:236` — `to_embed` 있을 때만 모델로드). 실측 대조:
- 변경분 3청크 있을 때 → **18.4s**(모델로드 발생)
- 직후 무변경 재실행 → **0.5s**(모델 미로드)

즉 07-19 인시던트가 잔여로 남긴 "무변경분 모델로드 16s 낭비"는 **이미 해결된 상태**였고, 진짜 원인은 다른 것이었다: **세션 시작 시점엔 직전 세션이 남긴 recent·open-loops·세션노트 변경분이 거의 항상 있어 스킵 경로에 안 걸린다.** 따라서 낭비가 아니라 *실제로 필요한* 임베딩 작업이며, 문제는 그것을 **사용자가 동기로 기다린 것**이다.

## 해결
`--reindex`를 **디태치**(비대기)로 전환 — session-end.ps1이 07-19부터 쓰던 검증된 패턴 그대로.
```powershell
Start-Process -FilePath 'py' -ArgumentList '-3', $searchPy, '--reindex' -WindowStyle Hidden -ErrorAction SilentlyContinue
```
**push(4)는 동기 유지** — 1.5s로 짧고, git 동시 실행은 index.lock 경합 위험(07-19 사례).
`HF_HUB_OFFLINE=1`은 **미채택** — 디태치 후엔 사용자가 안 기다리므로 체감 이득이 없고, 배포판 신규 설치에서 모델 최초 다운로드를 막아 깨뜨린다(§9 측정 우선).

### 검증 (PS 5.1로 실행 — §12.6 인코딩 2층 규정)
1. 파싱 OK(PS 5.1.26100), 한글 경로 리터럴 정상 판독 → BOM 보존 확인(UTF-8 BOM·LF 유지)
2. 훅 소요 **23s → 2.94s**(무변경 경로) / **1.85s**(실변경 존재 = 무거운 경로)
3. stdout 53줄·4,582자 = recent+open-loops+헬스 1줄만. **reindex 잡음 유입 0**(주입 컨텍스트 오염 없음)
4. 디태치 실증 2건: ① `hooks.log 23:16:29 fired` → `embeddings.json` mtime `23:16:30` ② 무거운 경로에서 훅이 1.85s에 반환한 뒤 자식(`py`→`python`)이 **+22.5s**에 인덱스 갱신 완료 = 부모 종료와 무관하게 완주. **이 22.5s가 종전에 사용자가 그대로 대기하던 시간.**

## 재발방지
- 07-19 원칙(**latency-bound 훅에 무거운 ML 금지**, 설계노트 §7 "훅=결정론적 추출·저장·커밋·검증만")이 SessionEnd에만 적용되고 **SessionStart에는 적용이 누락**돼 있었다. 훅 3종 전체에 적용 완료.
- 동시 실행 race(SessionStart 디태치 ↔ SessionEnd 디태치)는 **무해**: `save_index`가 tmp→`os.replace` 원자교체(`search.py:209`)라 손상 불가, 유실분은 다음 reindex가 hash 불일치로 자기치유. 이 race는 이번 변경 이전에도 존재했다.
- 잔여: HF Hub 확인 5.1s는 백그라운드로 밀렸을 뿐 사라지지 않았다. 배포판 신규설치 호환을 지키며 없애려면 "모델 캐시 존재 시에만 오프라인" 조건부가 필요 — 실수요 생기면 착수.

> [!info]- 관련 노트 %%sl%%
> [[incident-2026-07-19-SessionEnd-커밋정지]]
