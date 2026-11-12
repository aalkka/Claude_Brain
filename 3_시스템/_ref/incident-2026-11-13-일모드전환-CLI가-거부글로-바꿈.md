---
type: incident
title: 일 모드 전환 «전환»에 빨간 영어 거부 줄 — deny+interrupt 답을 CLI 가 고정 영어 글로 바꿔 적음
created: 2026-11-13
updated: 2026-11-13
tags: [외부뇌, 플러그인, brain-base, 대화창, incident]
주제: 외부뇌
aliases: []
links: []
status: resolved
confidence: verified
source: claude
---
# 일 모드 전환에 빨간 영어 거부 줄

## 증상
볼트 대화창 묻기 모드에서 일 모드 전환 카드의 «전환»을 누르면, 도구 줄 밑에 빨간 글로 `The user doesn't want to proceed with this tool use. The tool use was rejected …` 이 떴다. 사용자는 승인했는데 거부로 보였다.

## 근본원인
- 전환 카드는 이번 턴을 끊으려고 `can_use_tool` 에 `{behavior: "deny", message: <한국어 답>, interrupt: true}` 로 답한다(전환이면 턴이 끝난 뒤 같은 대화를 일 모드로 이어 감).
- `interrupt: true` 이면 CLI 가 `message` 대신 고정 영어 글을 `tool_result`(is_error)로 적는다. 지난 대화 기록 3건(`~/.claude/projects/<슬러그>/*.jsonl`)에서 확인 · 뒤에 `[Request interrupted by user for tool use]` 줄이 붙는다.
- 대화창 `toolResult` 는 is_error 결과를 모두 «거부·오류» 빨간 까닭 줄로 그렸다.

## 해결
brain-base 0.48.7: 도구 줄에 `data-tool` 을 달고, 일 모드 도구(`mcp__vault__work`) 결과는 빨간 줄·오류 표시 없이 닫기만 한다. 카드 답을 도구 줄에 «전환/전환 안 함» 표로 붙인다. 다른 도구의 거부는 그대로 빨간 줄(격리 시험으로 확인).

## 재발방지
- `interrupt: true` 로 답하는 다른 승인 카드를 만들면 같은 영어 글이 온다 — 결과를 그리는 쪽에서 그 도구를 갈라야 한다. 우리가 넣은 `message` 는 모델에게도 안 간다(모델은 영어 글을 받는다).
- 지난 대화 다시 그리기는 `[Request interrupted…]` 를 «멈춤»으로 그린다 — 일 모드 전환 턴이면 뜻이 다르다(미고침).
