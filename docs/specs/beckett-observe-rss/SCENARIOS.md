# SDD Scenarios: `beckett-observe-rss` Skill

**Companion spec:** `docs/specs/beckett-observe-rss/SPEC.md`  
**Date:** 2026-04-30

---

## Scenario S1: Guard triggers — config present and interval cooled

Given `~/.config/rss2email/config.cfg` exists  
And last RSS poll **≥90m** ago  
Then guard **triggered** with detail referencing interval readiness  

---

## Scenario S2: Guard skips — config missing

Given cfg absent  
Then guard **skipped** with detail referencing missing rss2email config  

---

## Scenario S3: Guard skips — cooldown active

Given cfg exists  
And `last_observe_rss` **<90m**  
Then guard not triggered  

---

## Scenario S4: Agent success

Given guard triggered stub `r2e` emits success exit `0`  
Then `RssResult` parses counts (or sentinel defaults documented)  
And `last_observe_rss` updated  

---

## Scenario S5: Agent failure — r2e nonzero exit

Given stub returns exit `!=0`  
Then skill records failure consistent with Beckett severity rules  

---

## Stress Tests

**T-R1 Idempotent rerun:** Repeated cycle within cooldown never spawns subprocess.  

**T-R2 Path portability:** Expanded home path resolves same on POSIX test harness.  

---

## Anti-Pattern Regression Signals

**Hard-coded hourly schedule inside guard** — violates interval-only principle.
