# dist-sync

볼트↔배포판↔사용자볼트 코어 동기화. 파일을 세 층으로 갈라 **개인 데이터를 건드리지 않고 코어만** 옮긴다.

- **설계 진실원본(볼트)**: [[외부뇌-dist-sync-모듈]]
- **결정(ADR)**: [[ADR-012-dist-sync-3층분류와-역할분담]]
- **파생·캐시**: `3_시스템/_index/dist-sync/` (gitignore — 볼트·push 오염 0)
- **스킬**: `/dist-sync:update`(받기) · `/dist-sync:publish`(보내기) (⚠ 신규 모듈은 **세션 재시작 후 활성**)

## 지금 되는 것 — 미리 보기, 승인 1번, 적용

진단과 계획은 볼트 내용을 고치지 않는다. 적용은 승인 뒤에 `fileops.py` 가 한다. 절차 = `skills/update/SKILL.md`.

```bash
py -3 .claude/skills/dist-sync/scripts/dist-diff.py --a <원본볼트> --b <대상볼트> --mode update|publish
```

사용자가 고친 코어는 판 해시 표(`known-hashes.json` · publish 때 `--build-known`)로 가려서 덮어쓰지 않는다. 합치고, 못 합치면 그대로 두고 묻는다. 근거 = ADR-030.

시험 = `py -3 3_시스템/_eval/update_sim.py --dist <배포판 worktree> --old <옛 판>` — 옛 판을 clone 한 가짜 사용자 볼트를 안내문의 명령 그대로 올린다.

## 왜 `git pull`이 아닌가

배포판이 추적하는 75파일 중 **사용자가 매일 쓰는 6개가 함께 추적된다**(`recent.md`·`open-loops.md`·`MOC.md`·`profile.md`·`CLAUDE.md`·`config.json`). git은 로컬 수정이 있으면 덮어쓰지 않고 **충돌을 낸다** → 업데이트가 멈추고 사용자는 초판에 갇힌다.

> 문서-코드 쌍둥이: 스펙과 코드가 어긋나면 **코드가 진실원본**. module-forge로 생성(2026-09-12).
