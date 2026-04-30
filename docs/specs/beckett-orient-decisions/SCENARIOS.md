# SDD Scenarios: `beckett-orient-decisions` Skill

**Companion spec:** `docs/specs/beckett-orient-decisions/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — interval + novelty

Given `≥30m` since `last_orient_decisions`  
And observation file touched after that timestamp  
Then guard triggers  

---

## Scenario S2: Guard skips — no novelty

Given interval satisfied  
But newest Memory markdown `mtime ≤ last_orient_decisions`  
Then guard **skipped** reporting no new observations  

---

## Scenario S3: Guard skips — cooldown

Given fresh observation exists  
But interval `<30m`  
Then cooldown skip  

---

## Scenario S4: Agent success

Given stub Claude JSON indicates `written` tasks equals Todoist creations count  

---

## Scenario S5: Agent failure budget

Given budget exceeded sentinel  
Then surfaced error propagated per runner semantics  

---

## Stress Tests

**T-OD1 Large batch:** Hundreds of touched files scanned without OOM path clarified.  

**T-OD2 Clock skew tolerance:** TZ consistency between PhaseState serde and mtimes documented.  

---

## Anti-Pattern Regression Signals

**Running without novelty check**, burning budget each cycle regardless of Observation delta.
