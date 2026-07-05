---
type: procedural
title: 상세 규격
status: active
---
# 프론트매터 스키마
type: semantic|episodic|procedural|decision|moc|incident
title, created, updated: ISO날짜, tags: [], links: []
status: active|archived (기본 active)
importance: 1-10 (선택, 정적. 기본 5)
confidence: verified|hypothesized (합성·인제스트물은 hypothesized)
source: user|pdf|session|claude
sensitive: true 시 push 제외

# 쓰기 위치
지식→2_지식/notes/ · 세션→sessions/ · 결정→decisions/ · 진단→3_시스템/_ref/

# incident 템플릿 (_ref/)
frontmatter(type:incident) + ## 증상 / ## 근본원인 / ## 해결 / ## 재발방지
