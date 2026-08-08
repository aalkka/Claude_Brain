---
name: module-forge
description: 외부뇌에 새 모듈(플러그인)을 만들거나 손볼 때 쓰는 개발조수. 사용자가 "모듈/플러그인 만들자", "이 기능을 외부뇌 확장으로", "모듈 충돌 검사" 같은 맥락을 보이면 발동. 실제 작업은 하위 스킬 `/module-forge:new`(설계→스캐폴드)와 `/module-forge:check`(충돌검사)로 위임한다.
---
# module-forge — 외부뇌 모듈 제작 조수 (오케스트레이터)

외부뇌에 붙는 새 모듈을 **설계부터 오류를 잡아내며** 빚어낸다. 자기 자신도 이 포맷으로 만든 dogfooding 플러그인. 설계 규율의 전문 = `rules-lib.md`.

## 2대 역할
- **① 설계조력 = 본체**: 단순 템플릿 채우기가 아니라 능동 co-design. 분해·경계·인터페이스를 함께 정하고, 효율 로드맵을 세우고, 과거 인시던트로 예방접종하고, 결정을 ADR로 남긴다. → `/module-forge:new` + `rules-lib.md`.
- **② 충돌방지 = 가드레일**: 신규 모듈이 기존 것과 부딪히지 않게 정적 검사(basename·경계·예약훅·의존). → `/module-forge:check` + `scripts/check.py`.

## 언제 무엇
| 상황 | 진입 |
|---|---|
| 새 모듈을 설계·생성 | `/module-forge:new <kebab-모듈명>` |
| 기존 모듈 충돌 재검사 | `/module-forge:check <모듈명>` |
| 네이티브 매니페스트 검증 | `claude plugin validate .claude/skills/<모듈명>` |

## 불가침 3 — RED LINE (위반 = 생성 거부)
- **I1 코어 무수정**: 모듈은 코어(`settings.json`·`3_시스템/hooks/*`·`search.py`·`.gitignore`·`CLAUDE.md`)를 건드리지 않는다.
- **I2 예약훅 금지**: 모듈은 `Stop`/`SessionStart`/`SessionEnd` 훅 등록 금지. 안전 이벤트(`PostToolUse`·`PreToolUse`·`UserPromptSubmit` 등)만.
- **I3 볼트 경계**: `module.json`의 `touches` 범위만 씀. `1_수집/**` 하드블록. 파생·캐시는 `3_시스템/_index/<모듈명>/`(gitignore 안). config는 모듈별 격리(코어 `config.json` 불가침).

## 하드규칙 (P0 실측)
1. **kebab 필수**: 모듈명은 kebab-case. `_` 접두 금지 — 로더가 스킵한다(CLI `plugin list`는 발견해도 인터랙티브 세션 미활성).
2. **재시작 후 활성**: 신규 모듈은 이 환경에서 `/reload-plugins` 미지원 → **생성 당일 세션엔 못 쓴다.** `new`는 반드시 "세션 재시작해야 활성" 안내로 끝난다. 자율 발동은 다음 세션부터.

## 산출 모듈 해부 (`new`가 만드는 것)
```
.claude/skills/<모듈명>/
├── .claude-plugin/plugin.json   # 네이티브 매니페스트(name·version·author·dependencies)
├── module.json                  # 외부뇌 확장계약(touches·forbids·invocation·surfaces)
├── skills/<스킬>/SKILL.md        # → /<모듈명>:<스킬>
├── hooks/hooks.json             # (선택) 안전 이벤트만
├── scripts/                     # (선택) ${CLAUDE_PLUGIN_ROOT} 참조
└── README.md                    # 볼트 설계노트 포인터
```
설계지식 쌍둥이 → `2_지식/notes/외부뇌-<모듈명>-모듈.md`(MOC 등재), 결정 → `2_지식/decisions/`.
