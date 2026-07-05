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

## 더 읽기
- **[사용자설명서](2_지식/notes/사용자설명서.md)** — 설치 후 어떻게 쓰나(간단). 일상 사용·스킬·구조.
- **[설계노트](2_지식/notes/설계노트.md)** — 왜 이렇게 만들었나(상세). 아키텍처·검색·설계 원칙·재구축 명세(§12).

## 구조 (알 필요 있는 것만)
- `1_수집/` = 내가 쓰는 곳 (시스템이 절대 수정 안 함)
- `2_지식/` = 뇌가 쌓는 지식 (노트·세션·결정)
- `3_시스템/` = 기계 (건드릴 필요 없음)
- 민감 노트는 frontmatter `sensitive: true` → push 제외.

## 라이선스·차용
차용 스킬(`obsidian-markdown`·`defuddle`) = kepano/obsidian-skills (MIT).
