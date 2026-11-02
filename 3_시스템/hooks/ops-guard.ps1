# 볼트 행위 가드 판정부(2026-10-29 · 볼트 개혁 피드백 1) — core-gate.ps1 이 «지우기·옮기기 동사 + 볼트 자리»를
# 함께 본 소수 경우에만 dot-source 한다(평소 호출은 이 파일을 파싱하지도 않는다). 호출자 스코프의 $p · $tool · $core 를 쓴다.
# 하는 일: 셸로 볼트 안을 지우기·옮기기·이름 바꾸기 하려는 명령을 막고(deny) fileops 사용법을 돌려준다.
#   왜 막나 — 그때그때 지은 rm·mv 는 흔적이 없고(장부) 지운 것이 사라지고(휴지통) 이름을 바꾸면 링크가 깨진다.
#   못 막는 것 — 대본 파일 안의 os.remove 등(명령 글자에 안 보임). 규칙(CLAUDE.md §2)이 덮는다.
# 실패 방향: fileops 가 없으면 통과(fail-open · ADR-006) — 가드가 볼트를 벽돌로 만들지 않게.
$vault = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$root  = if ($env:CORE_GATE_ROOT) { $env:CORE_GATE_ROOT } else { $vault }   # 검증 하네스는 샌드박스에서 돈다
$logf  = Join-Path $vault '3_시스템/_index/core-gate.log'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
if ($opsMode -eq 'apply') {           # fileops update·migrate --apply — 막지 않고 한 번 묻는다
    Add-Content -Path $logf -Value "$stamp [F] OPS-APPLY-ASK $tool" -ErrorAction SilentlyContinue
    @{ hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = 'ask'
        permissionDecisionReason = '업데이트·이전 적용 — 코어·폴더 구조를 한 명령으로 바꾼다. 미리 보기를 확인했으면 승인(되돌리기 = fileops undo <묶음 id> · 이전은 migrate --undo <id>).'
    } } | ConvertTo-Json -Depth 5 -Compress
    exit 0
}
if ($opsMode -eq 'obsidian' -and $p -match 'obsidian\S*\s+eval\b') {   # fileops 유무와 상관없이 막는다
    Add-Content -Path $logf -Value "$stamp [F] OBS-EVAL-DENY $tool" -ErrorAction SilentlyContinue
    @{ hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = 'deny'
        permissionDecisionReason = '⛔ 옵시디언 CLI eval 은 쓰지 않는다(2026-10-29 결정 — 앱 안 임의 코드 실행 = 금고 위협 모형). 화면은 command id=… · open, 볼트 행위는 fileops 로.'
    } } | ConvertTo-Json -Depth 5 -Compress
    exit 0
}
if (-not (Test-Path (Join-Path $root '3_시스템/fileops.py'))) {
    Add-Content -Path $logf -Value "$stamp [-] OPS-GUARD-OPEN(fileops 없음) $tool -" -ErrorAction SilentlyContinue
    return
}
# 코어를 건드리는 명령은 코어 게이트(승인)가 맡는다 — fileops 는 코어를 다루지 않는다(업데이터 몫).
if ($p -match ('(' + $core + ')')) { return }
# fileops 를 부르는 단독 명령 = 정상 경로. 다른 명령과 이어 붙였으면(; && |) 그 뒤를 못 믿으니 판정한다.
if ($p -match 'fileops\.py' -and $p -notmatch '(;|&&|\|)') { return }
# git rm --cached = 추적만 끊는다(파일은 그대로)
if ($p -match '\bgit\s+rm\b' -and $p -match '--cached') { return }
$short = if ($p.Length -gt 120) { $p.Substring(0, 120) + '…' } else { $p }
Add-Content -Path $logf -Value "$stamp [F] OPS-GUARD $tool $short" -ErrorAction SilentlyContinue
$reason = @'
⛔ 볼트 안 지우기·옮기기·이름 바꾸기는 fileops 로만 한다(CLAUDE.md §2 — 장부 자동 기록 · 휴지통 30일 · 링크 고침 · 되돌리기).
  py -3 3_시스템/fileops.py mv <원래> <새 자리> --why "까닭"
  py -3 3_시스템/fileops.py rm <경로> --why "까닭"
  그 밖: cp(들이기) · replace(덮어쓰기) · restore · undo · log · where — py -3 3_시스템/fileops.py -h
  미리 보기는 맨 앞에 --dry. 다른 명령과 잇지 말고(; && |) 따로 부른다. 휴지통 비우기(영구 삭제)는 사람만.
'@
@{ hookSpecificOutput = @{
    hookEventName            = 'PreToolUse'
    permissionDecision       = 'deny'
    permissionDecisionReason = $reason
} } | ConvertTo-Json -Depth 5 -Compress
exit 0
