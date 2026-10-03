---
type: incident
title: incident 2026-07-27 — Obsidian 블록수식 연속 시 수식 날것 노출
created: 2026-07-27
updated: 2026-07-27
tags: [incident, obsidian, 렌더, mathjax, 마크다운, study-helper, 진단]
links: ["[[incident-2026-07-26-obsidian-svg-style-stripping]]"]
status: active
importance: 6
confidence: verified
source: claude
---
# incident — Obsidian 블록수식 연속 → 수식 날것 노출

## 증상
사용자: "정리노트에 깨진글자 발생(이번세션 생성 정리노트 2개)". 확인 결과 **Obsidian에서 수식이 렌더되지 않고 LaTeX 소스가 그대로 노출**(`\mathbf`, `\tag{1.2}` 등).

## 원인
**`$$…$$` 한 줄 블록끼리 빈 줄 없이 연속되면** 마크다운 파서가 수식 구간 경계를 잘못 잡는다. 결과적으로 블록이 통째로 렌더에 실패한다.

```markdown
$$A_x = |\mathbf A|\cos\alpha \tag{1.2}$$
$$\mathbf A = A_x\hat{\mathbf x} \tag{1.3}$$   ← 앞 줄과 붙어 있으면 깨진다
```

## 진단 경로 — 대조군이 결정적이었다
| 노트 | 블록수식 연속 | 증상 |
|---|---|---|
| 벡터해석-Ch1 | **30건** | 깨짐 |
| 곡면좌표계-Ch2 | **27건** | 깨짐 |
| 복소해석-Ch3 | 0건 | 정상 |
| 선형대수-Ch4 | 0건 | 정상 |

**정상 노트(대조군)와 같은 스크립트로 비교**하자 후보가 한 번에 좁혀졌다. 대조군 없이 의심만 했을 때는 오진이 반복됐다.

### 오진 2회 (기록 — 같은 실수 반복 방지)
1. **`\tag` 남용 의심** — 깨진 노트 387회 vs 정상 16회로 **24배** 차이라 유력해 보였다. 그러나 정상인 Ch3에도 **같은 문법**(`$$…\tag{}$$` 한 줄)이 14건 있어 무죄.
2. **`\B`·`\V`·`\A`·`\C` undefined 명령 검출** — MathJax가 undefined control sequence를 만나면 블록 전체를 포기하므로 완벽한 설명처럼 보였다. 그러나 실제로는 **정규식 오탐**: 행렬 행구분 `\\` 뒤의 첫 글자(`\begin{pmatrix}A_x\\B_x\end{pmatrix}`)를 `\B`로 잡은 것.

- **인코딩·LaTeX 문법은 전부 정상이었다**(UTF-8 디코딩 OK, 이상문자 0, undefined 명령 0). 파일만 봐서는 원인이 안 보였다.

## 조치
1. 연속 블록 사이에 **빈 줄 57건 삽입**(Ch1 30 · Ch2 27). 블록 수·내용 무손실 검증.
2. **Stop 훅(`stop-check.ps1`)에 ④ 블록수식 연속 검사 추가** — MOC 미등재·프론트매터 누락과 같은 층위의 **종료 차단 게이트**. 규약(모델 준수)이 아니라 훅으로 강제.
   - 실증: 위반 파일 심음 → `블록수식 연속(...): file.md(1)` + `decision: block` / 제거 → 무출력 통과.
   - 순환 서킷브레이커 서명에도 편입(무한루프 방지).
3. `organize`·`illustrate` 스킬 + 학습노트 작성법 노트에 렌더 규칙 명문화.

## 재발방지 원칙
- **`$$…$$` 블록은 앞뒤로 빈 줄을 둔다.** (텍스트 직후 `$$`는 정상 노트에도 14건 전부 있었으므로 무죄 — **연속 케이스만** 문제.)
- **진단 시 대조군을 먼저 확보하라.** 증상 있는 것 vs 없는 것을 같은 스크립트로 비교해야 판별력이 선다.
- **검사 스크립트의 정규식도 검증 대상**이다(오탐으로 엉뚱한 범인을 만든다).

## 관련
- [[incident-2026-07-26-obsidian-svg-style-stripping]] — 같은 계열(Obsidian 렌더 제약을 몰라서 생긴 결함). 그때는 `<style>` 스트리핑으로 전 도형 검정.
- 진단 프로토콜 = 메모리 `feedback-troubleshooting-diagnose-protocol`(⑦대조군 확보·⑧체감≠실측 항목을 이 건에서 보강).

> [!info]- 관련 노트 %%sl%%
> [[incident-2026-07-26-obsidian-svg-style-stripping]]
