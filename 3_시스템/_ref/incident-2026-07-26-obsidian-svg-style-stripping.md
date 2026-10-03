---
type: episodic
title: incident — Obsidian 인라인 SVG의 <style> 제거로 전 도형 검정
created: 2026-07-26
tags: [incident, obsidian, svg, 렌더, study-helper, 도해]
status: active
---
# incident — Obsidian 인라인 SVG `<style>` 스트리핑 → 검정 박스

## 증상
study-helper `illustrate`가 만든 인라인 `<svg>`(class + `<style>` 블록 방식)를 Obsidian 노트에서 열자 **모든 도형이 검정**으로 렌더. 또 하단 통찰 텍스트가 **우측 잘림**. (챗/브라우저 렌더에선 정상 → Obsidian 특유.)

## 진단 (원인)
1. **`<style>` 제거**: Obsidian 마크다운 새니타이저가 인라인 SVG 내부 `<style>` 블록을 제거 → `.stack{fill:...}` 등 **class 기반 스타일 미적용** → SVG 기본 `fill`(검정)으로 폴백. → 전 도형 검정.
2. **텍스트 잘림**: 긴 한글 통찰 문장이 `viewBox` 폭 초과 + `svg`에 `width` 미지정으로 노트 폭 초과분 클리핑.

## 해결
- **`<style>`·class 전면 제거 → 모든 `fill`·`stroke`·`stroke-width`·`font-size`를 요소마다 인라인 presentation 속성**으로. (마커 fill도 인라인.) → Obsidian이 안 지움.
- **`@media prefers-color-scheme` 못 씀**(<style> 제거되니) → **테마-강건 팔레트**: 밝은 채움(`#eef2f7` 등) + 어두운 글자(`#0f172a`) → 라이트·다크 배경 양쪽서 읽힘.
- **`<svg width="100%" viewBox=...>`**(고정 width 금지) → 반응형, 가로 클리핑 방지.
- **긴 텍스트 = tspan 2줄 분할**, viewBox 폭 안으로.

## 재발방지
- **인라인 SVG를 Obsidian에 넣을 땐 `<style>`/class 쓰지 말 것 — 인라인 속성만.** (illustrate 스킬 「Obsidian 렌더 기술규칙 5항」에 코드화 = 결정론 재사용.)
- 삽입 전 렌더 검증(검정박스·잘림·테마 대비).
- Mermaid는 이 문제 없음(Obsidian 네이티브 처리) — 단순 도해는 Mermaid, 정밀·흐름 도해는 인라인-속성 SVG.

관련: study-helper 모듈의 illustrate 스킬 · 해당 도해가 실린 학습 노트(배포판 미포함).

> [!info]- 관련 노트 %%sl%%
> [[incident-2026-07-27-obsidian-블록수식-연속-날것노출]]
