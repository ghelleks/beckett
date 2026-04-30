# SDD Scenarios: `beckett-orient-meeting-prep` Skill

**Companion spec:** `docs/specs/beckett-orient-meeting-prep/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — upcoming meeting unseen

Given event E1 begins in **12h**  
And UID not previously recorded in PhaseState processed set  
And `≥30m` cooled  
Then guard triggers  

---

## Scenario S2: Guard skips — event already dedup processed

Given UID present in persisted processed set  
Then skip referencing dedupe  

---

## Scenario S3: Guard skips — no upcoming meetings in window

Given calendar empty forthcoming 24h  
Then skip  

---

## Scenario S4: Guard skips — interval active

Given events exist but `last_orient_meeting_prep` **`> now-30m`**  
Then cooldown skip  

---

## Scenario S5: Parallel successes

Given three eligible meetings and worker cap **`≥3`**  
Then `meetings_prepped==3` with three distinct agent subprocess ids captured in tests stub  

---

## Scenario S6: Partial agent failure one meeting

Given one stub nonzero exit  
Then aggregate policy increments partial failure vs total success enumerated  

---

## Stress Tests

**T-OMP1 Exploding recurring series:** expansion policy clarifies RRULE instantiation vs single master UID strategy.

---

## Anti-Pattern Regression Signals

Removing **UID dedupe** yields duplicate prep emails each loop.
