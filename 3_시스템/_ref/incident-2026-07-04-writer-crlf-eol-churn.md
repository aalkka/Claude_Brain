---
type: incident
title: B1 writer CRLF 라인엔딩 churn (search.py --link-write)
created: 2026-07-04
updated: 2026-07-04
tags: [외부뇌, incident, search, writer, git, eol, phase4.5]
status: active
source: session
---
# 인시던트: search.py B1 writer가 노트 라인엔딩을 뒤집어 git churn

## 증상
`search.py --link-write`(또는 SessionEnd 훅)가 노트에 `%%sl%%` 관리블록을 쓰면, 해당 노트 **전체가 git diff에서 "모든 줄 삭제+추가"**로 잡힘(내용은 동일). 6개 `notes/`·2개 `_ref/`가 미커밋 M 상태로 누적. B1 훅 배선 시 **매 세션 전체 라인 플립 반복** 예상.

## 근본원인
`open(path, "w", encoding="utf-8")`가 Windows 텍스트모드에서 `\n` → `\r\n` 변환. 반면 `read_text`는 universal newline으로 `\r\n` → `\n`으로 읽음. HEAD의 `.md` 일부가 CRLF인데 writer가 LF로(또는 그 반대) 재기록 → **전체 라인엔딩 플립**. 구 외부뇌 §3.6("자동 git 반복 sync": `.gitattributes` 부재 → CRLF 왕복 → git이 내용 동일 파일을 매번 변경으로 오인)의 **재발** — 신 볼트가 `.gitattributes`를 안 들고 온 회귀.

## 해결 (커밋 420773e)
1. writer: `open(..., "w", encoding="utf-8", newline="\n")` — LF 고정(Windows 변환 차단).
2. `.gitattributes` 신설: `*.md text eol=lf` + `*.py text eol=lf` (ps1은 BOM·인코딩 2층 민감 → 미포함).
3. `.md` 일괄 LF 정규화(`git add --renormalize`).

## 재발방지
- `.gitattributes` **삭제 금지**(삭제 시 churn 재발 — 구 §3.6).
- 볼트 파일을 쓰는 파이썬은 `newline="\n"` 명시(Windows 기본 CRLF 변환 방지).
- 검증: `--link-write` 2회 연속 실행 시 2번째 `git diff` 0(멱등 + EOL 안정).

> [!info]- 관련 노트 %%sl%%
> [[incident-2026-07-04-search-stdout-cp949]] · [[incident-2026-07-03-스펙-실측-괴리]]
