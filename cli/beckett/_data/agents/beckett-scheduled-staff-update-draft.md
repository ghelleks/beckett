---
name: beckett-scheduled-staff-update-draft
description: Friday staff newsletter draft leveraging /weekly-staff-update skill bundles.
allowed-tools:
  - Read
  - Bash
  - SlashCommand
---

Load ROLE + latest WorkBoard/context notes from `Memory/`. Draft witty leadership update referencing `/weekly-staff-update`; store draft under `Memory/Staff/` and echo `{ "done": true }`.

Do not mutate Reference or external repos unless ROLE explicitly permits.
