# SDD Scenarios: `beckett-scheduled` Aggregate

**Companion spec:** `docs/specs/beckett-scheduled/SPEC.md`  
**Date:** 2026-04-30

---

## Staff Update Draft (`beckett-scheduled-staff-update-draft`)

### Scenario S1: Trigger — Friday + 7d

Given today Friday local TZ AND `≥7d` since `last_scheduled_staff_update`  
Expect `invoke_claude_agent` dispatched + PhaseState bump  

### Scenario S2: Skip — wrong weekday

Given Monday even if timers satisfied  
Expect skip referencing weekday precondition  

### Scenario S3: Skip — cooldown <7d

Given Friday but last Friday run **`3d`** prior  
Expect skip  

---

## Efficiency Log (`beckett-scheduled-efficiency-log`)

### Scenario S4: Trigger — weekday cooled 24h

Given Tuesday & `≥24h` elapsed since prior log PhaseState stamp  
Expect shell subprocess append success & timestamp updated  

### Scenario S5: Skip — weekend suppression

Given Saturday  
Expect skip irrespective of timers  

---

## Efficiency Email (`beckett-scheduled-efficiency-email`)

### Scenario S6: Trigger triple conjunction

Weekday TRUE + **`≥24h` email cooldown** + **deterministic presence of today's log artifact** ⇒ send path executes & PhaseState bumped  

### Scenario S7: Skip missing log precondition

Timers satisfied but artifact absent ⇒ skip detail cites missing log prerequisite  

---

## Desktop Archive (`beckett-scheduled-desktop-archive`)

### Scenario S8: Trigger — 24h interval only

Cooldown satisfied even on weekends (unless overridden by future SPEC change) ⇒ agent dispatched  

### Scenario S9: Skip cooldown active

Elapsed `<24h` ⇒ suppressed  

---

## Stress Tests

**T-SCH1 Freeze-time TZ shift near midnight Friday boundary** verifies staff update guard correctness.  

**T-SCH2 Efficiency email+log ordering** prohibits email before preceding log emission if same cycle ordering misconfigured externally.  

---

## Anti-Pattern Regression Signals

**Hard-coded silent `09:00` guard** resurrecting hourly gating violates policy **M-SCH6**.
