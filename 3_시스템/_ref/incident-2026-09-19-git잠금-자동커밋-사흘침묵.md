---
type: incident
title: 죽은 git 잠금이 볼트 자동커밋을 사흘간 조용히 막았다
created: 2026-09-19
updated: 2026-09-19
status: resolved
confidence: verified
source: session
tags: [외부뇌, git, 훅, 자동커밋, incident]
links: []
---

## 증상

사용자가 「전부 커밋」이라 해서 볼트를 커밋하려 하자 —

```
fatal: Unable to create 'C:/Claude_Brain/.git/index.lock': File exists.
Another git process seems to be running in this repository, or the lock file may be stale
```

마지막 커밋이 **09-14**(`c62718b`)였고, 그 사이 세션이 여러 번 돌았는데 하나도 안 들어가 있었다.
세션 시작 상태에 수정·삭제 파일이 수십 건 쌓여 있던 것이 그 결과였다.

## 근본원인

`.git/index.lock` — **2026-09-16 23:20 자 · 0바이트**. 그리고 `.git/AUTO_MERGE.lock` 도 같이 남아 있었다.

- `tasklist`로 확인 = **git 프로세스 0개**
- `MERGE_HEAD` 없음 = **실제 병합 중이 아님**
- 크기 0바이트 = **쓰다 만 내용도 없음**

→ 09-16 에 무언가가 git 을 비정상 종료시키며 남긴 **죽은 잠금**이다.
그 뒤 Stop 훅의 자동커밋이 **매 턴 같은 오류로 실패**했다.

## ⛔ 왜 사흘이나 안 드러났나 — 신호는 있었다

SessionStart 훅이 매 세션 머리에 이미 띄우고 있었다:

```
[뇌] 노트 212개 | 인덱스 age 0d | 마지막커밋 5 days ago
```

**「마지막커밋 5 days ago」가 그 신호다.** 세션마다 커밋되는 볼트에서 5일은 정상이 아니다.
그런데 나는 그 줄을 배경 잡음으로 넘겼다. 자동커밋 실패 자체는 **아무 데도 보고되지 않는다** —
훅이 조용히 죽으면 조용히 끝난다.

## 해결

두 잠금 파일을 지우고 커밋했다(`4a43cbe`). 작업 내용 손실 0 — 잠금이 빈 파일이었고
작업트리는 그대로였다.

```bash
rm -f .git/index.lock .git/AUTO_MERGE.lock
```

## 재발 방지

- ⭐ **세션 머리의 「마지막커밋 N days ago」를 읽어라.** 볼트는 세션마다 커밋되므로
  **2일 이상이면 그 자체가 고장 신호**다. 지금 이 줄이 이미 있는데 안 읽은 것이 이 사고의 전부다.
- 잠금을 지우기 전에 **셋을 확인한다** — ⑴크기 0인가 ⑵git 프로세스가 도는가
  ⑶`MERGE_HEAD`·`REBASE_HEAD` 가 있는가. 셋 다 아니면 죽은 잠금이다.
  ⚠ 하나라도 걸리면 지우지 말고 보고한다 — 진행 중인 병합을 날릴 수 있다.
- ⚠ **자동커밋이 조용히 실패하는 구조가 남아 있다.** 훅이 커밋에 실패해도 세션은 그냥 끝난다.
  실패를 다음 세션 머리에 띄우는 것이 근본 수리다(미실행 · 열린 항목).
