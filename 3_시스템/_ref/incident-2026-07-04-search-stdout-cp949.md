---
type: incident
title: search.py stdout cp949 크래시 (비ASCII gist)
created: 2026-07-04
updated: 2026-07-04
tags: [외부뇌, incident, phase4, search, powershell, 인코딩]
status: active
source: session
---
# 인시던트: search.py 출력이 특수문자서 UnicodeEncodeError

## 증상
`python search.py --q "..." --mode hybrid` 실행 시 결과가 빈 출력. stderr 확인하니 `UnicodeEncodeError: 'cp949' codec can't encode character '—' (—) ...` 크래시. eval(`--eval`)은 hit@만 찍혀 안 걸렸음(경로는 한국어=cp949 인코딩 가능, 크래시 안 남).

## 근본원인
Windows 콘솔 stdout 기본 코드페이지 = **cp949**. `json.dumps(..., ensure_ascii=False)`로 gist를 그대로 출력 → gist에 **em-dash `—`(U+2014)** 등 cp949 미포함 문자가 있으면 인코딩 실패. 통찰노트 `MemGPT.md` 제목 "MemGPT — 가상 컨텍스트…"의 em-dash가 gist로 잡혀 발현. 인시던트 #6·#9(PS5.1 인코딩 2층)와 **동일 계열**: 파이썬 런타임 출력층도 Windows 기본 인코딩(cp949)에 물림.

## 해결
search.py 모듈 상단서 stdout·stderr를 UTF-8로 재설정:
```python
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): pass
```
검증: em-dash 든 gist 질의 정상 출력(MemGPT 통찰노트 rank1).

## 재발방지
- **Windows서 비ASCII 출력하는 파이썬 툴은 stdout `reconfigure(encoding="utf-8")` 필수.** cp949는 한글은 되나 em-dash·특수 유니코드 불가.
- 인코딩 검증은 **실제 런타임 경로**(콘솔 stdout)로. `2>/dev/null`·`| Out-Null`이 크래시 숨김 → eval만 돌리면 못 잡음. 스킬이 실제 소비하는 stdout 직접 확인.
- 3층 정리: ①.ps1 스크립트=UTF-8 BOM(#6) ②PS Get-Content 데이터read=`-Encoding UTF8`(#9) ③**파이썬 stdout=`reconfigure utf-8`(본건).** 전부 Windows 기본 인코딩(cp949/ANSI) 회피.
[[incident-2026-07-03-스펙-실측-괴리]]

> [!info]- 관련 노트 %%sl%%
> [[incident-2026-07-04-writer-crlf-eol-churn]] · [[incident-2026-07-03-스펙-실측-괴리]]
