# SDD Scenarios: `beckett-act` Skill

**Companion spec:** `docs/specs/beckett-act/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — @agent backlog

Given at least one open task `@agent` label present  

---

## Scenario S2: Guard triggers — @decision qualifier

Given comment includes configured decision marker sentinel  

---

## Scenario S3: Guard skips — empty queues

Given no qualifying tasks  

---

## Scenario S4: Agent executes simple closure

Given task maps to deterministic tool path only  
Then **`invoke_claude_agent` invocation count equals zero**

---

## Scenario S5: Agent delegates complex MCP

Given task body references multi-step ingestion  
Then `invoke_claude_agent` subprocess occurs once  

---

## Scenario S6: Partial failure sequencing

Given first tool raises; second succeeds  
Then **`failed>=1`** and **`executed>=1`** simultaneously with stable ordering logs  

---

## Scenario S7: Recurring completion

Given recurring template task completed  
Then next instance scheduled per Todoist API fixture  

---

## Stress Tests

**T-A1 Large queue:** deterministic chunking avoids token blow-up in planner preamble.

---

## Anti-Pattern Regression Signals

Greedy **`invoke_claude_agent` for arithmetic micro-ops**.
