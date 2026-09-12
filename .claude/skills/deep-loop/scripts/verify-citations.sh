#!/usr/bin/env bash
# 인용 검증 — deep-loop §6.2. 링크 생존 + 표기명↔실제 제목 대조.
#
#   verify-citations.sh <파일.md>     문서에서 [표기명](url) 쌍을 뽑아 대조
#   verify-citations.sh -u <urls.txt> URL 목록만 검사(한 줄에 하나)
#
# 자동화되는 것 = ⑴ 링크가 실제로 열리는가 ⑵ 표기한 제목이 실제 제목과 같은가.
# 자동화되지 않는 것 = ⑶ 그 자료가 그 주장을 실제로 하는가. 이건 사람/LLM 몫이다.
# 판정 기호: OK 일치 · ?? 대조필요(제목 미추출·표기 불일치) · !! HTTP 오류 · XX 연결 실패

set -u
TIMEOUT=20

# "<HTTP코드>\t<제목>" 한 줄을 반환한다. 서브셸에서 불리므로 변수로 내보내지 않는다.
probe_url() {
  # arXiv pdf/html → abs 로 정규화해야 제목이 잡힌다.
  local u="$1" probe body code t
  probe=$(sed -E 's#arxiv\.org/(pdf|html)/([0-9]{4}\.[0-9]{4,5}).*#arxiv.org/abs/\2#' <<<"$u")
  body=$(curl -sL --max-time "$TIMEOUT" -w '\n@@CODE@@%{http_code}' "$probe" 2>/dev/null || true)
  code=$(sed -n 's/.*@@CODE@@//p' <<<"$body" | tail -1)
  body=$(sed 's/@@CODE@@[0-9]*$//' <<<"$body" | tr -d '\n')
  t=$(grep -oP '(?<=<title>).*?(?=</title>)' <<<"$body" | head -1 || true)
  # substack·일부 SPA는 <title>이 비어 있고 og:title만 있다.
  [ -z "$t" ] && t=$(grep -oP '<meta[^>]+property="og:title"[^>]+content="\K[^"]+' <<<"$body" | head -1 || true)
  printf '%s\t%s' "${code:-000}" "$(cut -c1-110 <<<"$t")"
}

mark_of() {
  case "$1" in
    200) printf 'OK' ;;
    000|'') printf 'XX' ;;
    *)   printf '!!' ;;
  esac
}

if [ "${1:-}" = "-u" ]; then
  while read -r u; do
    [ -z "$u" ] && continue
    res=$(probe_url "$u"); code=${res%%$'\t'*}; t=${res#*$'\t'}
    m=$(mark_of "$code")
    [ -z "$t" ] && t='(제목 미추출 — 원문 확인 필요)'
    echo "$m $code | $u | $t"
  done < "${2:?urls.txt 경로가 필요하다}"
  exit 0
fi

grep -oP '\[[^]]+\]\(https?://[^)]+\)' "${1:?검사할 .md 경로가 필요하다}" | sort -u | while read -r pair; do
  label=$(sed 's/^\[//; s/\](.*//' <<<"$pair")
  url=$(sed 's/.*](//; s/)$//' <<<"$pair")
  res=$(probe_url "$url"); code=${res%%$'\t'*}; t=${res#*$'\t'}
  m=$(mark_of "$code")
  # 표기명에서 대조 키를 뽑는다 — 쉼표 앞 영문 제목부(‘Foo, arXiv 1234’ → ‘Foo’).
  key=$(sed 's/,.*//' <<<"$label" | grep -oP '^[A-Za-z][A-Za-z0-9 :\-]{3,}' | head -1 | xargs || true)
  if [ "$m" != "OK" ]; then v="$m"
  elif [ -z "$t" ]; then v='??'
  elif [ -n "$key" ] && grep -qiF "$key" <<<"$t"; then v='OK'
  else v='??'; fi
  echo "$v $code | 표기=[$label] | 실제=${t:-(미추출)}"
done
