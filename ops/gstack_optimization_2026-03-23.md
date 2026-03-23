# Gstack Optimization 2026-03-23

Project: x-ai-experts-viz
Target page: index_pre_1to1_latest_backup.html

## plan-ceo-review
Real user job is not "look at a graph".
Real user job is:
- quickly understand who matters in the current AI social graph
- trust why this sample is shown
- navigate back to the main product without getting lost
- use the page without reading developer notes

## plan-eng-review
High-value engineering fixes for this round:
- keep sample size synced with homepage `xai_expert_limit`
- make reset action clear filters + clear selection + restore overview
- expose sample size and update time in visible UI
- avoid hidden developer-centric states

## plan-design-review
Main design problems found before changes:
- top area lacked product framing, so page felt like a tool screen
- sample size and freshness were buried in sidebar only
- creator card felt developer-facing, not user-facing
- "return to overview" wording was too weak for real users

Design changes applied:
- added topbar product copy
- added visible meta pills for sample size and update time
- changed reset CTA to `清空并回到全景`
- repurposed creator card into `图谱使用提示`

## qa
Verified locally with browser automation on host-level port 8876:
- Top12 -> countExperts 12
- Top50 -> countExperts 50
- Top300 -> countExperts 300
- no selected profile on first load
- home link exists
- graph mode defaults to 3D

## remaining risk
- official gstack `browse` binary is not built because `bun` is missing
- data freshness warning remains: mitbunny_graph generated_at is stale
- public deployment still needs a stable sync step if latest local changes must go online
