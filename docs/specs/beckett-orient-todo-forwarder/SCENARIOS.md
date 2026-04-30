# SDD Scenarios: `beckett-orient-todo-forwarder` Skill

**Companion spec:** `docs/specs/beckett-orient-todo-forwarder/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — pending todo without forward tag

Given ≥1 Gmail fixture message labels `todo` ∧ ¬`todo-forwarded`  
And `≥15m` interval satisfied  
Then guard triggers  

---

## Scenario S2: Guard skips — all forwarded

Given all candidates already labeled `todo-forwarded`  
Then skip  

---

## Scenario S3: Guard skips — interval

Given backlog waits but cooldown active  
Then skip  

---

## Scenario S4: Success single message

Given raw retrieval + send stubs succeed sequentially  
Then `forwarded==1 failed==0` and label apply invoked  

---

## Scenario S5: Partial failure MIME too large

Given oversize triggers skip path increments `failed` with reason  

---

## Scenario S6: Idempotent replay

Given same Message-Id after success  
Then subsequent cycle `forwarded==0` and no duplicate send invocation counts  

---

## Stress Tests

**T-OTF1 Batch parallelism policy** clarified (likely sequential simplicity).  

---

## Anti-Pattern Regression Signals

Introducing summarization LLM **before forward** violates hard constraint **M-OTF1**.
