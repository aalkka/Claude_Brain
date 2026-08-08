---
name: check
description: 기존 외부뇌 모듈의 정적 충돌검사를 재실행한다. 사용자가 "모듈 충돌 검사", "이 모듈 괜찮나", "경계 위반 확인" 같은 맥락을 보이면 발동. basename 중복·1_수집 침범·예약훅·touches 겹침·deps 순환·surfaces 드리프트를 잡아 block/warn으로 보고.
---
# /module-forge:check <모듈명> — 정적 충돌검사 (가드레일)

신규·기존 모듈이 코어·다른 모듈과 부딪히지 않는지 정적으로 검사. 런타임 충돌(훅 실행순서·MCP 포트·`bin/` PATH)은 **범위 밖**(정직 — P4 연기).

## 실행
```bash
py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/check.py" <모듈명>
```
| 형태 | 용도 |
|---|---|
| `check.py <모듈명>` | 단일 모듈 검사 |
| `check.py --all` | 전 모듈 일괄(하나라도 block이면 exit 1) |
| `check.py <모듈명> --sync-surfaces` | `surfaces` 선언을 실제 스캔값으로 갱신 후 재검사 |
| `check.py <모듈명> --no-registry` | 레지스트리 재생성 생략(테스트용) |

출력 = `{"ok": bool, "blocks": [...], "warns": [...], "infos": [...]}`. **block 있으면 exit≠0.**
부산물 = `3_시스템/_index/modules.json` 레지스트리 재생성(gitignore=파생·재생성).

## 검사 항목 (P3② 완결 — 전종 실동작)

**block — 통과 불가**
| # | 검사 | 근거 |
|---|---|---|
| 1 | `_` 접두 모듈명 | 로더 스킵(P0 실측) — kebab 필수 |
| 2 | 모듈명 ↔ 코어 plain 스킬 동명 | 루트 SKILL.md가 plain 스킬 `<모듈>`로 등록 → 전역 오염 |
| 3 | 노트 basename 중복 | 위키링크 `[[name]]` 모호 ([[설계노트]] §12.6 로직 재활용) |
| 4 | `1_수집/**` 침범 (touches·스크립트 리터럴) | **I3** 사용자 저작물 불가침 |
| 5 | 예약훅 등록 (`Stop`/`SessionStart`/`SessionEnd`) | **I2** 코어 결정론·커밋 durability |
| 6 | 모듈간 `touches` **동일경로** | 소유권 모호 = 경계 붕괴 |
| 7 | `dependencies` 순환(DFS)·미존재 | 단방향 의존 강제 |
| 8 | `writes_config` 비어있지 않음 | **I3** 코어 config 불가침(A6 = config 모듈별 격리) |
| 9 | 스크립트가 코어파일 참조 (`3_시스템/config.json`·`hooks/`·`search.py`·`.claude/settings.json`·`CLAUDE.md`·`.gitignore`) | **I1** 코어 무수정 |
| 10 | 산출물 폴더 규약 위반 — `2_지식/notes/` 선언(코어 지식 전용) · `modules/` 루트 독점 · **타모듈 폴더 침범** | 모든 모듈이 `2_지식/modules/<모듈명>/`로 동일 형식 |

**warn — 통과하되 알림**
| 검사 | 뜻 |
|---|---|
| `module.json` 부재 | 볼트 쓰기경계 미선언 → 검사 대부분이 무음 통과 |
| `surfaces` 드리프트 | 선언 ↔ 실제 스캔 불일치(스킬 추가 후 미갱신). `--sync-surfaces`로 해소 |
| `touches` 포함관계 | 상위 경로 모듈이 하위를 덮음 → 경계 좁힐 것 |
| 스크립트 경로가 `touches` 밖 | 선언 밖 쓰기 의심 |
| 무관 basename 중복 | 이 모듈과 무관한 기존 중복(볼트 청소 권고) |
| `schema` 상회 | `module.json`이 이 검사기보다 새 스키마 → 검사기 갱신 필요(미지원 필드 무시 중) |

**infos** — 네임스페이스 열거(네이티브 `/<모듈>:<스킬>`가 이미 충돌차단 → 정보만) · 루트 SKILL.md의 plain 등록 · 훅 보유 시 런타임 한계 고지.

## forward-compat (P4 도입 대비)
`module.json`의 **모르는 키는 무시**한다 → 미래 필드를 미리 넣어도 검사기가 안 깨진다. 예약어 = `runtime`(MCP 포트·`bin/` PATH) · `router`(라우터 노출제어) · `marketplace`(배포 메타). 스키마 변경 시 `schema` 값을 올리면 **구버전 검사기가 warn으로 자백**한다. 출력 계약(`ok`/`blocks`/`warns`/`infos`)은 **키 추가만 허용·기존 키 의미 불변**.

## block 시 조치
- **basename 중복** → 노트/모듈명을 고유 basename으로 개명.
- **1_수집 침범** → `touches`·스크립트에서 제거. 사용자 저작물은 불가침(승격만).
- **예약훅** → `hooks.json`을 안전 이벤트(`PostToolUse`·`PreToolUse`·`UserPromptSubmit` 등)로 교체.
- **touches 동일경로** → 한쪽을 하위 경로로 좁히거나 소유 모듈을 정한다.
- **deps 순환** → 공통부를 제3 모듈로 빼거나 의존 방향을 하나 끊는다.

## 정직한 한계 (범위 밖)
- **런타임 충돌** 미검출: 훅 실행순서·MCP 포트·`bin/` PATH — P4 연기.
- **Claude 세션 쓰기는 정적 귀속 불가**: SKILL.md 프로즈를 읽고 Claude가 쓰는 경로는 추적 못 한다. `touches` 준수 검증은 **모듈 스크립트(결정론 코드)** 범위만.
- 리터럴 스캔은 '언급'과 '접근'을 구분 못 함 → 주석·글로브(`*`)는 제외, 필요 시 줄에 `mf:allow-path`(줄 제외)·파일 상단 40줄 내 `mf:allow-path-file`(파일 제외) 표식.

## 회귀 테스트 (가드레일이 실제로 막는지)
```bash
py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/test_check.py"
```
픽스처 모듈을 실제로 생성해 각 위반이 **기대대로 차단되는지** 대조 후 삭제(정리 `finally` 보장). 정상 모듈=ok·exit 계약·실모듈 회귀 포함. **check.py를 고쳤으면 이걸 돌려라** — "산출물 존재 ≠ 게이트 통과".
