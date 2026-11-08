#!/bin/sh
# pre-commit 민감 노트·키 회귀 시험(11-03) · 실행: sh 3_시스템/_eval/precommit_sensitive_check.sh — 격리 저장소에서 실제 훅으로 이름을 바꾸며 민감 표시·키를 넣어도 커밋에 안 들어가는지
HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/pre-commit"
T=$(mktemp -d)
cd "$T" || exit 2
git init -q
git config user.name t
git config user.email t@t
git config core.quotepath false
cp "$HOOK" .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
BODY="본문 줄 하나
본문 줄 둘
본문 줄 셋
본문 줄 넷
본문 줄 다섯
"
pass=0
all=0
ok() { all=$((all + 1)); if [ "$2" = "0" ]; then pass=$((pass + 1)); echo "통과 $1"; else echo "실패 $1"; fi; }

printf -- '---\ntitle: 가\n---\n%s' "$BODY" > 가.md
printf -- '---\ntitle: 일반\n---\n%s' "$BODY" > 일반.md
git add -A && git commit -qm 처음 >/dev/null

# 이름 바꾸기 + 민감 표시
git mv 가.md 나.md
printf -- '---\ntitle: 나\nsensitive: true\n---\n%s' "$BODY" > 나.md
git add -A
git commit -qm 이름바꿈 >/dev/null 2>&1
git ls-tree -r --name-only HEAD | grep -q '^나\.md$'
[ $? -ne 0 ]; ok "이름 바꾸며 민감 표시 = 커밋에 안 듦" $?
[ -f 나.md ]; ok "민감 노트 파일은 그대로" $?
git ls-files --error-unmatch 나.md >/dev/null 2>&1
[ $? -ne 0 ]; ok "민감 노트 = 추적 밖" $?

# 새 민감 노트
printf -- '---\ntitle: 새\nsensitive: true\n---\n%s' "$BODY" > 새.md
printf -- '---\ntitle: 같이\n---\n%s' "$BODY" > 같이.md
git add -A
git commit -qm 새것 >/dev/null 2>&1
git ls-tree -r --name-only HEAD | grep -q '^새\.md$'
[ $? -ne 0 ]; ok "새 민감 노트 = 커밋에 안 듦" $?
git ls-tree -r --name-only HEAD | grep -q '^같이\.md$'; ok "같이 담은 일반 노트 = 들어감" $?

# 이름 바꾸기 + 키
git mv 일반.md 바뀜.md
# 키 글자를 나눈다 — 이 대본도 볼트에 커밋된다. 붙여 쓰면 pre-commit 이 이 파일을 잡아 볼트 자동 커밋이 멈춘다(11-03)
printf -- '---\ntitle: 바뀜\n---\n%skey %s\n' "$BODY" "sk-""abcdefghijklmnopqrstuvwx" > 바뀜.md
git add -A
git commit -qm 키 >/dev/null 2>&1
[ $? -ne 0 ]; ok "이름 바꾸며 키 = 커밋 막힘" $?

cd / && rm -rf "$T"
echo "$pass/$all"
[ "$pass" = "$all" ]
