# 외부뇌 (External Brain)

Obsidian 볼트 + Claude Code 개인 지식 시스템. 토큰 최적화·맥락 복원·답변 질을 위한 1인 지식관리.

## 필수 요건
- **Windows** (훅이 PowerShell — 현재 Windows 전용. 타 OS는 훅 스크립트 포팅 필요)
- git · Claude Code v2.1.59+ · Obsidian
- **Python 3.10+** + `sentence-transformers`(하이브리드 검색) + `markitdown`(PDF 인제스트).
  첫 검색 시 임베딩 모델(기본 `intfloat/multilingual-e5-small`, ~470MB)을 자동 내려받아 로컬 인덱스를 만든다.

## 설치
1. 템플릿 clone → **즉시 main 브랜치 생성**(태그 clone은 detached HEAD — 이 단계 없으면 세션 커밋이 고아가 되고 push가 영구 실패):
   ```
   git clone <repo> --branch v0-template <내볼트경로>
   cd <내볼트경로>
   git switch -c main
   ```
2. **git 훅 활성**(secret 차단 게이트):
   ```
   git config core.hooksPath 3_시스템/hooks
   ```
   (미실행 시 secret-scan 안 돎.)
3. **Python 의존성**:
   ```
   py -3 -m pip install sentence-transformers markitdown
   ```
   (`sentence-transformers`=하이브리드 검색 · `markitdown`=PDF 인제스트. 강GPU가 bge-m3 티어로 올릴 때만 CUDA torch 별도:
   `py -3 -m pip install torch --index-url https://download.pytorch.org/whl/cu121`)
4. **첫 인덱스 빌드**(최초 1회 수동 — 모델 ~470MB 다운로드 + 임베딩이 세션 훅 타임아웃을 넘길 수 있어 수동 권장):
   ```
   py -3 3_시스템/search.py --rebuild
   ```
5. Obsidian에서 이 폴더를 볼트로 열기.
6. 폴더에서 `claude` 실행 → 트러스트 수락.
7. 첫 세션에 "⚠ 개인화 미완료" → `setup-interview` 실행(~10분). **네이티브 메모리 볼트 리다이렉트(옵션R)**·호칭·언어·톤·하드웨어(임베딩 모델 자동)·**개인 백업 repo 연결**.
   → **개인 repo를 연결하기 전까지 자동 push는 비활성**(개인정보 보호). 인터뷰가 `origin`을 개인 repo로 설정한다.
8. 끝. 이후 그냥 대화. 재보정은 언제든 `/재보정`.

## 업데이트 — 새 배포판이 나왔을 때

> **먼저 읽을 것.** 업데이트는 «내 볼트에 배포판의 **코어만** 덮어쓰고, 내가 쓴 것은 건드리지 않는 일»이다. `git pull`로 하면 안 된다 — 배포판이 추적하는 파일 중 `recent.md`·`open-loops.md`·`MOC.md`·`profile.md`·`CLAUDE.md`·`3_시스템/config.json` 여섯은 **설치 후 내가 매일 쓰는 파일**이라 충돌이 나고 업데이트가 멈춘다.

### 파일은 네 층이다 (이 표가 전부다)

| 층 | 무엇 | 업데이트 때 |
|---|---|---|
| **코어** | `.claude/skills/**` · `.claude/settings.json` · `.claude/output-styles/**` · `3_시스템/hooks/**` · `3_시스템/search.py` · `session-stub.py` · `tokens.py` · `conventions.md` · `3_시스템/_ref/**` · `3_시스템/_eval/**` | **덮어쓴다** |
| **씨앗** | `2_지식/recent.md` · `open-loops.md` · `MOC.md` · `profile.md` · `3_시스템/config.json` · `2_지식/notes/설계노트.md` · `사용자설명서.md` | **덮어쓰지 않는다.** 위쪽 머리말(사용법 안내)만 새것으로 바꾸고 그 아래 내가 쓴 항목은 그대로 둔다 |
| **`CLAUDE.md`** | — | **§0(내 호칭·말투)만 남기고 나머지를 새것으로.** 한 파일에 섞여 있어 자동 복사 불가 |
| **개인** | `1_수집/**` · `2_지식/notes·sessions·decisions·modules/**` · `3_시스템/_index/**` · `3_시스템/_claude-memory/**` · `.claude/settings.local.json` | **열지도 않는다** |

---

### A. 업데이터가 없는 버전 (`.claude/skills/dist-sync/` 폴더가 없으면 이쪽)

전부 git 명령이다. **순서대로** 실행한다. 경로에 한글이 있으므로 따옴표를 그대로 둔다.

**1단계 — 지금 상태를 저장한다 (되돌릴 수 있게)**

```bash
cd <내볼트경로>
git add -A && git commit -m "update 전 상태 저장" || echo "커밋할 변경 없음 — 그대로 진행"
git branch backup-before-update
```

`git branch`가 만드는 것은 되돌림 지점이다. 업데이트가 잘못되면 `git reset --hard backup-before-update`로 전부 되돌린다.

**2단계 — 배포판을 원격으로 추가하고 받아온다 (내 파일은 아직 안 바뀐다)**

```bash
git remote add dist <설치할 때 clone 한 그 URL>
git fetch dist
```

- 이미 있다는 오류(`remote dist already exists`)가 나면 정상이다. `git fetch dist`만 실행한다.
- `origin`은 내 개인 백업 repo다. **건드리지 않는다.**

**3단계 — 무엇이 바뀌는지 먼저 본다 (아직 아무것도 안 바뀐다)**

```bash
git diff --stat HEAD dist/main -- .claude/ "3_시스템/" CLAUDE.md
```

삭제 목록은 **반드시 «내가 설치한 시점»을 기준으로** 뽑는다. 그 시점 이후 배포판이 실제로 지운 것만 골라내기 위해서다.

```bash
BASE=$(git merge-base HEAD dist/main) && echo "설치 기준점: $BASE" && git diff --name-status $BASE dist/main -- .claude/ "3_시스템/" .obsidian/ | grep "^D"
```

아무것도 안 나오면 삭제분이 없는 것이다. 나온 것이 5단계에서 지울 목록이다.

> ⛔ **`git diff --name-status HEAD dist/main | grep "^D"` 를 쓰면 안 된다.** 그 `D`는 «배포판이 지운 것»이 아니라 «배포판에 없는 내 파일»이고, 거기에는 **내가 직접 만든 노트·스킬이 전부 섞여 들어온다.** 실측(제작자 볼트): 올바른 기준으로 0건인데 `HEAD` 기준으로는 **51건**이 나왔다. 그대로 지웠다면 내 파일 51개가 사라진다.
>
> `merge-base`가 아무것도 출력하지 않으면(공통 조상 없음 — shallow clone 등) **삭제 단계를 건너뛰고** 4·6단계만 한다. 없어진 파일이 남아 있어도 시스템은 돈다.

**4단계 — 코어만 덮어쓴다**

```bash
git checkout dist/main -- .claude/skills .claude/settings.json .claude/output-styles
git checkout dist/main -- "3_시스템/hooks" "3_시스템/search.py" "3_시스템/session-stub.py" "3_시스템/tokens.py" "3_시스템/conventions.md" "3_시스템/_ref" "3_시스템/_eval"
```

- 배포판에 없는 경로를 적으면 `pathspec did not match` 오류가 난다. 그 경로만 빼고 다시 실행하면 된다.
- **씨앗·개인 층 경로는 이 명령에 절대 넣지 않는다.**

**5단계 — 없어진 파일을 지운다**

3단계에서 `D`로 나온 것을 지운다. `git checkout`은 덮어쓰기만 하고 삭제는 하지 않으므로 이 단계가 필요하다. 초판에서 올라오는 경우 예시:

```bash
rm -rf .claude/skills/obsidian-markdown .claude/skills/session-close
```

⚠ **`.obsidian/plugins/` 아래는 지우지 않는다.** 배포판에서 빠진 것일 뿐, 내가 계속 써도 되는 Obsidian 플러그인이다.

**6단계 — `CLAUDE.md`를 손으로 합친다 (자동 복사 금지)**

```bash
git show dist/main:CLAUDE.md > /tmp/CLAUDE-new.md
```

`/tmp/CLAUDE-new.md`(새것)와 내 `CLAUDE.md`를 나란히 열고, **내 `## §0 사용자` 절만 그대로 유지한 채 나머지를 새것으로 바꾼다.** §0에는 내 호칭·언어·톤이 들어 있고 그건 `setup-interview`가 채운 내 것이다.

Claude에게 맡기려면 이렇게 말하면 된다: *"`/tmp/CLAUDE-new.md`가 새 배포판 규약이야. 내 CLAUDE.md의 §0만 그대로 두고 나머지를 새것에 맞춰 갱신해줘."*

**7단계 — 씨앗 파일의 머리말만 갱신한다 (선택)**

건너뛰어도 시스템은 돈다. 규약 안내문이 낡은 채로 남을 뿐이다. 하려면 파일마다:

```bash
git show dist/main:2_지식/recent.md
```

로 새 버전을 띄워 **맨 위 제목·인용구(사용법 안내)만** 내 파일에 옮겨 적는다. **그 아래 내가 쓴 줄은 한 줄도 건드리지 않는다.**

**8단계 — 확인하고 커밋한다**

```bash
git status --short
```

여기에 `1_수집/`·`2_지식/notes/`·`sessions/`·`decisions/`·`_index/`·`_claude-memory/` 경로가 **하나라도 보이면 잘못된 것이다.** 즉시 멈추고 `git reset --hard backup-before-update`로 되돌린다.

문제없으면:

```bash
git add -A && git commit -m "update: 배포판 코어 반영"
```

**9단계 — 새 세션으로 다시 연다**

스킬·훅 변경은 **세션을 다시 시작해야 적용된다.** `claude`를 껐다 켠다. 첫 세션에서 `claude plugin list`로 스킬이 보이는지 확인한다.

되돌리려면 언제든:

```bash
git reset --hard backup-before-update
```

---

### B. 업데이터가 있는 버전 (`.claude/skills/dist-sync/` 폴더가 있으면 이쪽)

**1단계 — 배포판을 받아온다** (A의 2단계와 같다. 내 파일은 안 바뀐다)

```bash
git remote add dist <설치할 때 clone 한 그 URL>
git fetch dist
git worktree add ../brain-dist dist/main
```

마지막 줄은 배포판을 **내 볼트 밖 옆 폴더**에 펼친다. 내 볼트는 그대로다.

**2단계 — 되돌림 지점을 만든다** (A의 1단계와 같다)

```bash
git add -A && git commit -m "update 전 상태 저장" || echo "커밋할 변경 없음"
git branch backup-before-update
```

**3단계 — 진단을 돌린다 (파일을 고치지 않는다)**

```bash
py -3 .claude/skills/dist-sync/scripts/dist-diff.py --a ../brain-dist --b . --mode update --out "3_시스템/_index/dist-sync/update.md"
```

`3_시스템/_index/dist-sync/update.md`에 리포트가 생긴다. 또는 Claude에게 *"업데이트 있어?"* 라고만 해도 된다 — `dist-sync:update` 스킬이 위 명령을 대신 실행한다.

**4단계 — 리포트에서 이 셋을 먼저 본다**

- **「⛔ 대상 볼트에만 있는 파일」** — **지울 목록이 아니다.** 배포판이 제거한 것과 **내가 직접 만든 것**이 섞여 있고 진단은 둘을 구분하지 못한다. 실제로 지울 것은 A의 3단계 `merge-base` 명령으로 따로 뽑는다.
- **「미분류」** — 층 규칙에 없는 파일이다. 판단이 설 때까지 옮기지 않는다.
- **「코어 — 내용 다름」** — 여기에 **내가 직접 고친 파일이 섞여 있을 수 있다.** 덮어쓰면 내 수정이 사라진다. 고친 기억이 있으면 그 파일만 따로 빼둔다.

**5단계 — 적용은 A의 4~8단계 그대로**

현재 버전의 업데이터는 **진단까지만** 한다(의도적이다 — 볼트마다 상태가 달라 자동 적용이 안전하다고 확인되기 전에는 열지 않는다). 리포트를 근거로 A의 4~8단계를 실행한다. Claude에게 맡기려면 리포트를 보여주며 이렇게 말한다:

> *"이 리포트의 «코어» 층만 `git checkout dist/main -- <경로>`로 가져오고, 씨앗·개인 층은 건드리지 마. `CLAUDE.md`는 §0만 남기고 갱신해줘. 삭제 목록은 하나씩 확인받고 지워."*

**6단계 — 뒷정리와 확인**

```bash
git worktree remove ../brain-dist
git status --short
```

`status`에 개인 층 경로가 보이면 잘못된 것이다. `git reset --hard backup-before-update`로 되돌린다.

**7단계 — 새 세션으로 다시 연다.** (A의 9단계와 같다)

---

### 업데이트가 잘못됐을 때

```bash
git reset --hard backup-before-update
```

1단계에서 만든 지점으로 전부 돌아간다. 그 뒤 처음부터 다시 하거나, 그냥 두고 써도 된다 — **업데이트는 선택이고, 안 해도 기존 볼트는 그대로 돌아간다.**

## 더 읽기
- **[사용자설명서](2_지식/notes/사용자설명서.md)** — 설치 후 어떻게 쓰나(간단). 일상 사용·스킬·구조.
- **[설계노트](2_지식/notes/설계노트.md)** — 왜 이렇게 만들었나(상세). 아키텍처·검색·설계 원칙·재구축 명세(§12).

## 구조 (알 필요 있는 것만)
- `1_수집/` = 내가 쓰는 곳 (시스템이 절대 수정 안 함)
- `2_지식/` = 뇌가 쌓는 지식 (노트·세션·결정)
- `3_시스템/` = 기계 (건드릴 필요 없음)
- 민감 노트는 frontmatter `sensitive: true` → push 제외.

## 라이선스·차용
이 저장소 = MIT — [LICENSE](LICENSE).
차용 스킬(`defuddle`) = kepano/obsidian-skills (MIT).
