# Beckett Loop Scenarios

## S1: Valid single-role one-shot

- Role has `loop.yaml`.
- All registry entries resolve.
- At least one guard triggers.
- `beckett loop --once --role-target work` exits `0`.
- `work/.ooda-state/last-run.json` exists and contains triggered/total counts.

## S2: OODA-only role fails

- Role has `OODA.md` but no `loop.*`.
- `beckett doctor` reports `loop_spec` failure.
- `beckett loop --once --role-target <role>` exits `1`.

## S3: Multi-role continue-on-failure

- Three roles discovered.
- One role has invalid spec (fatal).
- Remaining roles still execute.
- Process exits `1`.

## S4: Partial failures

- Spec loads and registry resolves.
- One agent raises runtime error.
- Remaining entries continue.
- Process exits `2`.
- Successful outputs from other entries are still committed.

## S5: No changes no commit

- No guard triggers and no files are modified.
- Loop run completes without creating a new commit.

## S6: Memory write-local enforcement

- Non-synthesis skill attempts to write outside role memory root.
- Runtime rejects write with `MemoryWriteError`.

## S7: Personal synthesis write policy

- `mask-ooda-orient-synthesis` in `personal` role writes to `personal/Memory/Synthesis/`.
- Same write attempt from other skills is rejected.

## S8: Status output

- `last-run.json` exists: status shows run timestamp, triggered count, success.
- Missing `last-run.json`: status reports `never`.
