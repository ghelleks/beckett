# SDD Scenarios: `beckett-orient-email` Skill

**Companion spec:** `docs/specs/beckett-orient-email/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — inbox eligible after interval

Given two accounts configured  
And Account A unread_count>0 → eligible true  
And `≥15m` elapsed since last email orient  
Then guard triggers referencing eligible account(s)  

---

## Scenario S2: Guard skips — inbox_guard false for all accounts

Given all accounts unread_count triggers ineligible sentinel  
Then guard skips even if cooldown satisfied  

---

## Scenario S3: Guard skips — 15m cooldown

Given unread exists but cooldown active  
Then skip detail cites interval  

---

## Scenario S4: Parallel success

Given stub emits success per account differing classification counts  
Then `accounts_processed == eligible_count`  

---

## Scenario S5: Partial failure

Given Account B stub errors  
Then documented policy selects either exit code **2 partial** vs aggregate failure fields  

---

## Stress Tests

**T-OE1 Max accounts:** Validates worker cap & orderly shutdown.  

**T-OE2 Token isolation:** Credential leakage sniff test absent cross-env echo.  

---

## Anti-Pattern Regression Signals

**Serializing MCP calls sequentially** unnecessarily when policy mandates parallel-safe operations.
