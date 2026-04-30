# SDD Scenarios: `beckett-orient-post-meeting` Skill

**Companion spec:** `docs/specs/beckett-orient-post-meeting/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — recent end + unseen UID

Given meeting ended **`30m` ago**, UID absent from processed-set, interval cooled  

---

## Scenario S2: Guard skips — too old

Given meeting ended **`120m` ago**
Then temporal skip  

---

## Scenario S3: Guard skips — dedup UID

Given UID processed previously  
Then skip  

---

## Scenario S4: Agent success tasks

Given stub JSON tasks_created aligns with Todoist creations count fixtures  

---

## Scenario S5: Missing transcript graceful path

Given transcript absent policy branch fires skip or fallback metric increments explicit field  

---

## Scenario S6: Cooldown suppression

Given meetings eligible but `last_post_meeting <30m ago`  

---

## Stress Tests

**T-OPM1 Back-to-back meetings:** ordering independence + stable dedupe.

---

## Anti-Pattern Regression Signals

Silent **zero-task** exits without logging skip rationale when transcript unavailable.
