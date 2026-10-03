---
type: incident
title: B1 writer CRLF 라인엔딩 churn (search.py --link-write)
created: 2026-07-04
updated: 2026-07-28
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

## 재발 (2026-07-27, `.ps1` 계층)
**위 재발방지 2번째 항목이 지켜지지 않았다.** 기본값에 맡긴 것도 아니고 **정반대로 `newline="\r\n"`을 명시**했다.

- **경위**: Claude가 Bash 힙독 파이썬으로 `stop-check.ps1`을 패치하며 `io.open(p,"w",encoding="utf-8-sig",newline="\r\n")`로 전체 재작성(07-27 05:07:13·05:08:29 UTC). 7초 뒤 커밋 `cdc51de`가 CRLF 상태를 그대로 담았다. BOM은 `utf-8-sig`로 지켰으나 EOL에서 어긋났다.
- **실피해**: 저장소가 CRLF로 오염 → 배포판(LF)과 갈려 이식 때마다 **235줄 가짜 diff**. `.md`는 `.gitattributes`가 막아줬지만 `.ps1`은 대상 밖이라 무방비였다.
- **뿌리**: 재발방지 규칙이 이 `_ref` 문서에만 있고 **강제층이 없었다** = 모델 의존 → 죽은 규약(설계노트 뿌리②). 문서 규칙을 더 쓰는 것으로는 또 죽는다.

### 시정 — git 계층에서 강제
`.gitattributes`에 `*.ps1 text eol=lf` 추가 + `git add --renormalize -- '*.ps1'`. 이제 파이썬이 CRLF로 써도 **커밋 시 LF로 정규화**되어 저장소·배포판 오염이 차단된다(작업트리 CRLF는 남을 수 있으나 실피해는 커밋본이므로 충분). 영향 파일 = `stop-check.ps1` 1개(나머지 2개는 이미 LF).

**구 주석의 배제 근거("ps1은 BOM·인코딩 2층 민감")는 실측으로 기각.** 격리 repo 라운드트립:

| 검증 | 결과 |
|---|---|
| 저장소 정규화 | CRLF+BOM → **LF+BOM** (162B = LF본과 완전 동일) |
| 체크아웃 왕복 | BOM 보존·LF·크기 동일 |
| PS 5.1 파싱 | BOM+CRLF / BOM+LF / BOM없음 3종 전부 OK |
| PS 5.1 **실행** | `[뇌] 노트 {{슬롯}} 개` 정상 출력 — 한글·`{{}}`슬롯 판독 무손상 |
| 재정규화 후 `git status` | clean (churn 없음) |

`eol=lf`는 EOL 바이트만 바꾸고 BOM(`EF BB BF`)은 건드리지 않는다. 실볼트 적용 후에도 `stop-check.ps1` BOM 유지·PS 5.1 파싱 OK·Stop 훅 실행 시 stdout 공백(계약 준수) 확인.

### 범인 판별 (실측, 무죄 확정분)
`Write` 도구=LF · `Edit` 도구=기존 EOL 유지 · `search.py --link-write`=전체 LF · **Obsidian**=LF 파일 편집 후 LF 유지 · **git**=`.md`엔 LF 강제, `.ps1`엔 무변환. **CRLF 생성이 확인된 것은 PowerShell `Set-Content`와 위 파이썬 `newline="\r\n"`뿐.**

**미확정 잔여**: 개인 노트 2개의 **혼합 EOL**(본문 CRLF + `%%sl%%` 블록 2줄만 LF). `newline=''`(EOL 보존)로 읽어 일부만 치환한 스크립트가 유력하나 미검증. 실피해 0(`.gitattributes`가 커밋본을 LF로 정규화)이라 추적 중단.

> [!info]- 관련 노트 %%sl%%
> [[incident-2026-08-08-StartProcess-디태치-569ms]]
