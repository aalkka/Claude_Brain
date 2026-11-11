# 외부뇌 (External Brain)

Obsidian 볼트 + Claude Code 개인 지식 시스템. 토큰 최적화·맥락 복원·답변 질을 위한 1인 지식관리.

## 필수 요건
- **Windows** (훅이 PowerShell — 현재 Windows 전용. 타 OS는 훅 스크립트 포팅 필요)
- **Git for Windows**(Git Bash 포함 — 훅 하나가 Bash 문법) · Claude Code v2.1.59+(구독 로그인) · Obsidian
- 선택: Node.js(웹페이지 읽기 도구 `defuddle`) · MS Word(docx 를 PDF 로) · 크롬(수집 창이 글을 여는 브라우저)
- **Python 3.10+** + `sentence-transformers`(하이브리드 검색) + `markitdown`·`pypdfium2`·`pillow`·`olefile`(원본 색인 — PDF·Office·한글·그림).
  첫 검색 시 임베딩 모델(기본 `intfloat/multilingual-e5-small`, ~470MB)을 자동 내려받아 로컬 인덱스를 만든다.

## 설치
1. 템플릿 clone → **즉시 main 브랜치 생성**(태그 clone은 detached HEAD — 이 단계 없으면 세션 커밋이 고아가 되고 push가 영구 실패):
   ```
   git clone <repo> --branch v3-template <내볼트경로>
   cd <내볼트경로>
   git switch -c main
   ```
2. **git 훅 활성**(secret 차단 게이트) **+ 이름·메일**(자동 커밋에 필요 · 이 볼트에만):
   ```
   git config core.hooksPath 3_시스템/hooks
   git config user.name "<이름>"
   git config user.email "<메일>"
   ```
   (훅을 안 켜면 secret-scan 이 조용히 안 돈다 — 건강 줄이 «볼트 밖 설정 안 됨»으로 알린다.)
3. **Python 의존성**:
   ```
   py -3 -m pip install sentence-transformers "markitdown[docx,pptx,xlsx]" pypdfium2 pillow olefile
   ```
   (`sentence-transformers`=하이브리드 검색 · 나머지 = `3_시스템/ingest.py` 원본 색인(PDF 글자·쪽 그림 · docx·pptx·xlsx · hwp). 그림 쪽 글자는 윈도우 내장 OCR 로 읽는다(한국어 윈도우면 설치 없음 · 아니면 설정 › 시간 및 언어 › 언어 추가 › 한국어 · «광학 문자 인식» 체크). 강GPU가 bge-m3 티어로 올릴 때만 CUDA torch 별도:
   `py -3 -m pip install torch --index-url https://download.pytorch.org/whl/cu121`)
4. **첫 인덱스 빌드**(최초 1회 수동 — 모델 ~470MB 다운로드 + 임베딩이 세션 훅 타임아웃을 넘길 수 있어 수동 권장):
   ```
   py -3 3_시스템/search.py --rebuild
   ```
5. Obsidian에서 이 폴더를 볼트로 열기. «제한 모드 끄기(커뮤니티 플러그인 켜기)»를 고르면 동봉 플러그인 **Brain Source**가 켜진다 — 원본(PDF·docx·pptx·xlsx·hwp·csv·html)을 옵시디언 안에서 보고 고치고, 엑셀식 `.sheet` 를 편집하고, 같은 이름 md 를 원본 아래 메모 칸으로 붙인다. 원본은 기본으로 보호(읽기 전용) 상태로 열린다.
   (선택) 옵시디언 설정 › 일반 › «명령줄 인터페이스» 켜기 — 파일을 옮길 때 옵시디언이 링크를 함께 고친다.
6. 폴더에서 `claude` 실행 → 트러스트 수락(«Yes, proceed») → `/login` 으로 Claude 구독 계정 로그인(API 키 환경 변수는 두지 않는다).
7. 첫 세션에 "⚠ 개인화 미완료" → `setup-interview` 실행(~10분). **네이티브 메모리 볼트 리다이렉트(옵션R)**·호칭·언어·톤·하드웨어(임베딩 모델 자동)·**개인 백업 repo 연결**.
   → **개인 repo를 연결하기 전까지 자동 push는 비활성**(개인정보 보호). 인터뷰가 `origin`을 개인 repo로 설정한다.
8. **볼트 밖 설정 점검** — Claude 에게 «바깥 설정 점검». 빠진 설치·설정을 재서 Claude 가 할 수 있는 것은 묻고 대신 하고, 사람이 할 것(앱 화면·로그인·관리자 권한)은 한 단계씩 안내한다. 목록 = `.claude/skills/dist-sync/external.json`.
   이 판에 없는 것: 받는 문(탐색기 우클릭·`Ctrl+Alt+B` — 실행 파일 없음 · 대신 옵시디언 `1_수집/받은함` 폴더로 끌기) · 학교 LMS 수집 · 웹 공지 정기 받기(수집 창 «지금 받기»로 받는다).
9. 끝. 옵시디언에서 **홈 › 관리 › 튜토리얼**로 실제 화면에서 한 단계씩 익힌다. 재보정은 언제든 `/재보정`.

## 업데이트 — 새 배포판이 나왔을 때

> **2026-11 판은 폴더 체계가 바뀌었다** — `notes` → `분야` · `sessions` → `기록` · `decisions` → `일/외부뇌/결정` · `1_수집/학교` → `배움`. 업데이터가 이전 파일(`3_시스템/migrations/`)로 옮기고, 링크와 옵시디언 설정(책갈피·그래프·열린 탭)을 고치고, 되돌릴 수 있다.

> **먼저 읽을 것.** 업데이트는 «내 볼트에 배포판의 코어를 들이고, 내가 쓰고 고친 것은 지키는 일»이다. `git pull`로 하면 안 된다 — 배포판이 추적하는 파일 중 `recent.md`·`open-loops.md`·`MOC.md`·`profile.md`·`CLAUDE.md`·`3_시스템/config.json` 여섯은 **설치 후 내가 매일 쓰는 파일**이라 충돌이 나고 업데이트가 멈춘다. `git checkout dist/main -- <경로>` 로 골라 받는 것도 안 된다 — 코어 대본끼리 서로 기대고 있어 빠진 파일이 있으면 찾기·기록이 멈춘다.

### 파일은 네 층이다 (이 표가 전부다)

| 층 | 무엇 | 업데이트 때 |
|---|---|---|
| **코어** | `.claude/skills/**` · `.claude/settings.json` · `.claude/output-styles/**` · `3_시스템/hooks/**` · `3_시스템/search.py` · `session-stub.py` · `tokens.py` · `conventions.md` · 코어 대본(`fileops`·`brain`·`roles`·`follow` 등) · `ingest.py` · `ingest_vision.py` · `3_시스템/_ref/**` · `3_시스템/_eval/**` · `.gitignore` · `.gitattributes` · 동봉 플러그인(설정 `data.json` 제외) | **안 고친 파일은 새 판으로.** 내가 고친 파일은 내 수정과 합치고, 못 합치면 그대로 두고 묻는다. 옛 판은 휴지통(30일). 배포판이 뺀 파일은 안 고친 것만 휴지통으로. 내가 만든 파일은 손대지 않는다 |
| **씨앗** | `2_지식/recent.md` · `open-loops.md` · `MOC.md` · `profile.md` · `3_시스템/config.json` · `2_지식/주제.md` · `보존.md` · `2_지식/일/외부뇌/설계노트.md` · `사용자설명서.md` | **덮어쓰지 않는다.** 뿌리 칸에 없는 것만 넣는다. 머리말(사용법 안내)을 새로 하고 싶으면 손으로 |
| **`CLAUDE.md`** | — | **§0(내 호칭·말투)은 그대로, 나머지는 새것으로.** §0 밖에 내가 더한 줄이 있으면 합치고, 못 합치면 그대로 두고 묻는다 |
| **개인** | `1_수집/**` · `2_지식` 의 나머지 · `3_시스템/_index/**` · `3_시스템/_claude-memory/**` · `.claude/settings.local.json` · `.obsidian/plugins/*/data.json` | **내용을 바꾸지 않는다.** 폴더 체계가 바뀔 때만 이전 파일대로 옮기고 경로 링크를 고친다 |

내가 고쳤는지는 배포판에 실린 판 해시 표(`.claude/skills/dist-sync/known-hashes.json`)로 가른다. 과거 공개 판과 같으면 안 고친 파일이다. 줄바꿈 차이는 고친 것으로 치지 않는다.

---

### 순서 (어느 판에서 올라오든 같다)

**1단계 — 지금 상태를 저장한다**

```bash
cd <내볼트경로>
git add -A && git commit -m "update 전 상태 저장" || echo "커밋할 변경 없음 — 그대로 진행"
```

**2단계 — 배포판을 내 볼트 옆 폴더에 펼친다 (내 파일은 안 바뀐다)**

```bash
git remote add dist <설치할 때 clone 한 그 URL>
git fetch dist
git worktree add ../brain-dist dist/main
```

- 이미 있다는 오류(`remote dist already exists`)가 나면 정상이다. 나머지 줄만 실행한다.
- `origin`은 내 개인 백업 repo다. **건드리지 않는다.**

**3단계 — Claude 에게 맡긴다**

> *"`../brain-dist/.claude/skills/dist-sync/skills/update/SKILL.md` 절차대로 이 볼트를 업데이트해줘."*

내 볼트의 업데이트 스킬이 «P0 = 진단뿐»이라고 말하면 옛 판이다. 위 파일이 맞다. 절차는 미리 보기 → 내 승인 1번 → 적용이고, 승인 전에는 아무것도 바뀌지 않는다.

**4단계 — 미리 보기에서 이 넷을 먼저 본다**

- **못 합친 파일** — 내 수정과 배포판 변경이 같은 곳에 있다. 파일마다 그대로 둘지, 새 판으로 할지, Claude 가 합친 안을 볼지 고른다.
- **내 수정과 합친 파일** — 내가 고친 기억이 맞는지.
- **배포판이 뺀 파일** — 휴지통으로 간다(30일).
- **이전** — 무엇이 어디로 가는지와, 고치지 않고 알리기만 하는 옛 경로(기억·플러그인 설정·내 대본).

**5단계 — Obsidian 을 닫고 승인한다**

켜 둔 Obsidian 은 플러그인 목록과 열린 탭을 자기 기억으로 다시 쓴다. 처음 들어오는 플러그인은 켜지 않으며, 켜도 지금 배치와 기본 탐색기를 바꾸지 않는다(새 탐색기는 Brain Base 설정 «기본 탐색기 대신 쓰기»).

**6단계 — 뒷정리**

```bash
git worktree remove ../brain-dist
```

**7단계 — 새 세션으로 다시 연다.** 스킬·훅 변경은 **세션을 다시 시작해야 적용된다.** Claude 에게 찾기 색인 다시 만들기를 맡긴다(옮긴 자리를 찾기가 알게 · 몇 분 걸림).

손으로 하려면 3~5단계 대신 이렇게 한다.

```bash
py -3 ../brain-dist/.claude/skills/dist-sync/scripts/dist-diff.py --a ../brain-dist --b . --mode update --out "3_시스템/_index/dist-sync/update.md" --plan-out "3_시스템/_index/dist-sync/update-plan.json"
py -3 ../brain-dist/3_시스템/fileops.py --vault . update "3_시스템/_index/dist-sync/update-plan.json"
py -3 ../brain-dist/3_시스템/fileops.py --vault . migrate --from ../brain-dist/3_시스템/migrations
```

여기까지는 미리 보기다. `3_시스템/_index/dist-sync/update.md` 를 읽은 뒤 Obsidian 을 닫고 적용한다.

```bash
py -3 ../brain-dist/3_시스템/fileops.py --vault . update "3_시스템/_index/dist-sync/update-plan.json" --apply
py -3 ../brain-dist/.claude/skills/dist-sync/scripts/dist-diff.py --a ../brain-dist --b . --apply-plugins
py -3 3_시스템/fileops.py migrate --apply
```

---

### 업데이트가 잘못됐을 때

이전을 먼저, 그다음 업데이트를 되돌린다. 묶음 id 는 적용할 때 출력에 나온다.

```bash
py -3 3_시스템/fileops.py migrate --undo 0001-목적별-다섯-영역
py -3 ../brain-dist/3_시스템/fileops.py --vault . undo <묶음 id>
```

⛔ **`git reset --hard` 로 되돌리지 않는다.** md 아닌 원본(PDF 등)은 git 밖이라 돌아오지 않고 노트만 돌아가서, 노트가 두 자리에 겹치고 원본 링크가 깨진다. 이전 뒤 `git status` 에 `2_지식`·`1_수집` 경로가 보이는 것은 **정상**이다. 플러그인 교체는 되돌리기 밖이다(설정은 그대로이고, 판만 새것).

업데이트는 선택이다. 안 해도 기존 볼트는 그대로 돌아간다.

## 더 읽기
- **[사용자설명서](2_지식/일/외부뇌/사용자설명서.md)** — 설치 후 어떻게 쓰나. 읽는 문서가 아니라 튜토리얼 시작점.
- **[찾아보기](3_시스템/tutorial/찾아보기.md)** — 하고 싶은 일에서 방법 찾기. 대화창의 Claude 도 이것을 읽고 답한다.
- **[설계노트](2_지식/일/외부뇌/설계노트.md)** — 왜 이렇게 만들었나(상세). 아키텍처·검색·설계 원칙·재구축 명세(§12).

## 구조 (알 필요 있는 것만)
- `1_수집/` = 받은 원본 (내용은 시스템이 고치지 않음 · 옮기고 지우면 시스템이 따라감)
- `0_작업/` = 진행 중인 작업 · `2_지식/` = 뇌가 쌓는 지식 (목적별 영역 배움·일·생활·분야 · 기록 · 일정)
- `3_시스템/` = 기계 (건드릴 필요 없음)
- 민감 노트는 frontmatter `sensitive: true` → push 제외.

## 라이선스·차용
이 저장소 = MIT — [LICENSE](LICENSE).
동봉 플러그인 Brain Source(`.obsidian/plugins/brain-source/`) = Apache-2.0 — 같은 폴더 `LICENSE`. 번들에 묶인 오픈소스 127개(Univer·ExcelJS·docx-preview·pdf-lib·rhwp·React 등 — MIT·Apache-2.0·ISC·0BSD · 이중 라이선스는 MIT 쪽)의 고지 = 같은 폴더 `THIRD_PARTY_NOTICES.md`.
차용 스킬(`defuddle`) = kepano/obsidian-skills (MIT).
