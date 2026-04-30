# SDD Scenarios: `beckett-observe` Skill

**Companion spec:** `docs/specs/beckett-observe/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — pending marker present

Given `deps.role_dir/.beckett-pending/observer.txt` exists  
And last observe was `<` 90m ago and inbox is quiet  
Then guard returns **triggered: true** with detail referencing marker  

---

## Scenario S2: Guard triggers — 90m interval elapsed

Given no marker  
And unread mail absent (`signals` empty)  
And `PhaseState.last_observe` is **≥ 90 minutes** ago or **None**  
Then guard triggers with detail citing interval elapsed  

---

## Scenario S3: Guard skips — interval not cooled

Given marker absent  
And unread absent  
And `last_observe` within **90m** window  
Then guard returns **triggered: false**, detail cites cooldown  

---

## Scenario S4: Agent success — observations materialized

Given guard triggered  
When agent runs against fixtures with deterministic tool stubs  
Then `ObserveResult.files_written ≥ 1` implies `signals_found ≥ 1` correlation  
And new markdown files reside under `<role>/Memory/` only  
And `Memory/INDEX.md` reflects additions (shared helper contract)  

---

## Scenario S5: Agent dedupe — silent no-op counts

Given identical replay signal payload  
Then `files_written == 0` while `signals_found` may be > 0  

---

## Scenario S6: Failure — tool outage

Given Todoist CLI returns nonzero  
Then agent catches / surfaces error; runner marks skill failure consistent with partial failure policy  

---

## Stress Tests

**T-O1 Dedupe correctness:** Repeated identical ingestion across N cycles yields ONE observation file baseline (plus explicit UPDATE path if modeled).  

**T-O2 Marker atomicity:** Removing marker AFTER successful run prevents immediate re-trigger until interval or unread condition returns.  

---

## Anti-Pattern Regression Signals

**Hour-of-day branching inside observe guard** — violates Guard Contract (`beckett-loop` SPEC). Maps to **M-O5**.

**Writes outside `/Memory`** — violates memory sandbox. Maps memory policy.
