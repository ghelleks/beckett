# SDD Scenarios: `beckett-observe-context-refresh` Skill

**Companion spec:** `docs/specs/beckett-observe-context-refresh/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — 72h boundary

Given PhaseState lacks `last_observe_context_refresh` **or** value **≥72h** old  
Then guard triggers  

---

## Scenario S2: Guard skips — within window

Given last refresh `<72h`  
Then guard suppressed with cooldown detail  

---

## Scenario S3: Agent success

Given sentinel `claude` stub returns JSON matching `ContextRefreshResult`  
Then files reviewed >0 **or** documented zero-scan fast path unchanged  
And `updated` increments only when CONTEXT touched  

---

## Scenario S4: Agent failure — bad JSON

Given stub prints narrative text stdout only  
Then parse failure → Beckett treats as execution error per runner policy  

---

## Scenario S5: Dry-run omission

Given `--dry-run`  
Then `invoke_claude_agent` never scheduled  

---

## Stress Tests

**T-CR1 Large Memory tree:** Bounded budget ensures termination / partial policy explicit.  

**T-CR2 Concurrent roles:** Separate PhaseState prevents cross-blocking.  

---

## Anti-Pattern Regression Signals

Embedding **business-hours gate** directly in guard.
