---
type: incident
title: 배포판에 넣은 플러그인 번들(main.js)을 Windows git autocrlf 가 clone 때 CRLF 로 바꿈
created: 2026-10-13
status: resolved
source: session
tags: [incident, dist-sync, git, autocrlf, gitattributes, brain-sheet]
links: []
---

# 배포판 플러그인 번들 줄바꿈 변환 (10-13)

- **증상**: 배포판(공개 저장소)에 Brain Sheet 플러그인 `main.js`(esbuild 압축 번들 14.5MB)를 넣고 새 태그로 clone 해 보니 빌드와 **480바이트** 달랐다. `manifest.json`(+9)·`styles.css`(+295)도 줄 수만큼 커졌다.
- **근본 원인**: Windows git 전역 `core.autocrlf = true`. 저장소의 `.gitattributes` 는 `*.md`·`*.py`·`*.ps1` 만 `eol=lf` 로 정하고 `.js` 는 정하지 않아, checkout 때 LF 480개가 CRLF 로 바뀌었다. 압축 번들의 줄바꿈은 대부분 템플릿 문자열 안에 있으므로 문자열 값이 바뀔 수 있다(동작 차이는 재지 않았다 — 바뀌기 전에 막음).
- **발견**: push 뒤 «새 설치자처럼» 태그를 실제로 clone 해 `cmp` 로 빌드와 대조했을 때. 커밋한 blob 자체는 LF 그대로였다(작업 폴더에 `cp` 로 넣고 커밋) — 문제는 받는 쪽 checkout 에서만 생긴다.
- **해결**: 배포판 `.gitattributes` 에 `.obsidian/plugins/brain-sheet/main.js binary`(줄바꿈 변환·줄 단위 diff 모두 끔). 업데이트 절차는 플러그인을 받기 전에 `git checkout dist/main -- .gitattributes` 부터. 고친 뒤 새 clone = main.js 빌드와 바이트 동일.
- **재발 방지**:
  - 배포판에 생성물(번들·압축 파일)을 넣을 때는 그 경로를 `.gitattributes` 에 `binary` 로 먼저 적는다.
  - 공개 직후 «새 설치자 경로»(문서의 설치 명령 그대로 clone)를 실제로 돌려 바이트를 대조한다 — 작업 폴더 대조로는 안 보인다.
  - 같은 clone 에서 주석 태그(`git tag -a`)가 `clone --branch` 때 «is not a commit» 경고를 내는 것도 잡았다. 설치용 태그는 기존 것과 같은 가벼운 태그로.
