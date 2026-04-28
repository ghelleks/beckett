# Blog Style Guide

This guide defines the structure, tone, and formatting rules for every blog
post in `docs/_posts/`. All posts must follow it. A PR that adds or changes a
component without a matching post is incomplete (see `AGENTS.md`).

---

## Tone

- **Practical and direct.** Written for a developer who wants to get something
  working, not read theory.
- **Second person ("you")** throughout — not "the user" or "one".
- **No jargon without explanation.** Define every Beckett-specific term on
  first use in the post (you cannot assume the reader has read other posts).

---

## Required Sections

Every post must contain these sections, in this order:

| Section | Purpose | Length |
|---------|---------|--------|
| **The Problem** | End-user pain point, no Beckett terminology yet | 2–4 sentences |
| **The Component** | What this part of Beckett is; how it addresses the problem | 1 paragraph |
| **How It Works** | Mechanism: bullets or short paragraphs | 3–8 items |
| **Walkthrough** | Numbered, copy-pasteable steps from zero to working | All steps shown with commands and expected output |
| **What You Get** | End state the reader is now in | 1–3 sentences |
| **Further Reading** *(optional)* | Links to related posts in this series | — |

---

## Front Matter Template

Every post must use this front matter:

```yaml
---
layout: post
title: "<verb phrase describing what the reader will accomplish>"
date: YYYY-MM-DD
categories: [components]
excerpt: "<one sentence completing: 'In this post you will learn how to...'>"
---
```

---

## Formatting Rules

**Headings**
- Use `##` (H2) for all section headings inside a post.
- Do not use H3 or deeper — keep posts flat and scannable.

**Code blocks**
- Always specify the language: ` ```bash `, ` ```yaml `, ` ```markdown `,
  ` ```text `.
- Show the shell prompt (`$`) for commands the reader runs.
- Show expected output immediately below the command in the same block,
  separated by a blank line.

```bash
$ beckett doctor

[PASS] ooda_agenda: all roles parseable
[PASS] guards_executable: all guards present
```

**Inline formatting**
- **Bold** for file names and UI labels (e.g., **OODA.md**, **Observe**).
- Backticks for commands and paths (e.g., `beckett run`, `guards/ooda-act.sh`).

**Tables**
- Only use tables when comparing more than three items side by side.
- Never use a table when a bulleted list would be clearer.

**Length**
- 500–900 words per post, not counting code blocks.
- If you need more than 900 words, split into two posts.

---

## Walkthrough Requirements

The Walkthrough section is the most important part of every post. Follow these
rules:

1. Number every step (`1.`, `2.`, etc.).
2. Every step that requires a command must show the command and its expected
   output in a `bash` code block.
3. Steps must be runnable from top to bottom with no gaps — do not skip
   prerequisite steps (installation, environment setup).
4. If a step varies by platform or configuration, note the variation inline,
   not in a footnote.
5. End the walkthrough at the moment the reader has verified the feature is
   working — not before.

---

## What Not to Do

- Do not start a post with "In this blog post..." — start directly with the
  problem.
- Do not use passive voice in the Problem or Walkthrough sections.
- Do not include architecture diagrams — prose and code blocks only.
- Do not reference GitHub issue numbers or internal task IDs.
- Do not add comments to code blocks unless the comment is essential to
  understanding an output line.
