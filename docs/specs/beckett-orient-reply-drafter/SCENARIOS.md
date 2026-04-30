# SDD Scenarios: `beckett-orient-reply-drafter` Skill

**Companion spec:** `docs/specs/beckett-orient-reply-drafter/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — dependencies satisfied

Given `last_orient_email` populated  
And qualifying without-draft thread fixtures  
And interval cooled  
Then triggers  

---

## Scenario S2: Guard skips — email phase never ran PhaseState sentinel

Given `last_orient_email is None` (initial state)  
Then skip citing dependency ordering  

---

## Scenario S3: Guard skips — all threads already drafted

Given heuristics confirm drafts exist for all labeled threads  
Then skip  

---

## Scenario S4: Agent success drafts

Given stub returns `drafts_created = N` and Gmail drafts count matches  

---

## Scenario S5: Heuristic ambiguity failure

Given API edge returns partial data  
Then deterministic failure path enumerated (explicit error vs cautious skip documented)  

---

## Stress Tests

**T-ORD1 Thread explosion:** truncation policy surfaced in result.detail.

---

## Anti-Pattern Regression Signals

LLM probing for draft existence **violates** deterministic guard requirement.
