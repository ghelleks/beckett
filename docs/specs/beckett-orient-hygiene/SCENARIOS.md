# SDD Scenarios: `beckett-orient-hygiene` Skill

**Companion spec:** `docs/specs/beckett-orient-hygiene/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — label populated + interval

Given deterministic stub shows ≥1 labeled thread  
And `≥20m` since last hygiene  
Then triggers  

---

## Scenario S2: Guard skips — label empty

Given label count zero  
Then skip labeling reason  

---

## Scenario S3: Guard skips — cooldown

Given backlog exists but cooldown **<20m**  
Then skip referencing interval  

---

## Scenario S4: Agent success

Given stub modifies labels / archives sample threads  
Then `threads_reviewed` aligns with enumerated thread IDs length  

---

## Scenario S5: Agent failure MCP denial

Given tool permission denied sentinel  
Then failure maps to Beckett severity policy  

---

## Stress Tests

**T-OH1 Large backlog:** truncation + explicit backlog remainder metric.

---

## Anti-Pattern Regression Signals

LLM-evaluating unread counts **instead of** deterministic `gws`.
