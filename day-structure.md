# Day Task Structure

How a prep day is laid out as study material + problem pages (the Notion-side hierarchy), and how many problems each day type carries. The Pre-Submit Ritual and 4-Stage Solving Template referenced here are defined in [SKILL.md](SKILL.md).


Every prep day is organized as a 3-layer hierarchy. This forces separation of *understanding the concepts* from *practicing them*, and gives every problem its own scratchpad.

```
Day N parent (~ Focus + Output, minimal)
├── Day N Sub — Review – <topic>
│     (concept review: must-know concepts + common patterns, ~15-30 min reading)
└── Day N Sub — Challenges – <count> <type> problems (~90 min)
      ├── DN-P1 — <problem name>
      ├── DN-P2 — <problem name>
      └── ... (each problem = its own page with solving slots)
```

### Parent body (minimal)

```
## Focus
<1-2 sentences naming the concepts/skills>

## Output
<1-2 sentences naming success criteria>
```

Do not duplicate concept content or problem lists in the parent — they belong in the sub-tasks.

### Review sub-task body

**Write the actual study material directly into the page in the user's language.** Do NOT use file-pointer checklists ("read these files"). The user reads the Notion page to study; the skill files are only a deep-dive reference.

```
# Review Concept — <topic>

## Goal
<2-3 sentences naming the mental model + reflex to build>

## Must-know concepts
### 1. <Concept 1 name>
<full explanation, 2-4 paragraphs, with embedded code where useful>
### 2. <Concept 2 name>
...

## Common patterns
### <Pattern name>
```code with comments```
<short explanation of when to reach for this pattern, what trap it avoids>

## Common-mistake reference table
| Wrong code | Symptom | Fix |
|---|---|---|
...

## Today's Pre-Submit Ritual focus
<the 4 questions, contextualized to this day's content>

## Full skill reference (for detail lookups)
<absolute path to the relevant skill file — single line, last in the page>
```

**Conventions:**
- Write prose in the user's language; keep code English.
- Use code blocks generously — concrete > abstract.
- Use a "common-mistake reference table" with three columns (wrong code / symptom / fix) for the day's common traps. Easy to scan.
- Skill file path goes at the BOTTOM as a single reference line, not as a checklist of sections to read.
- Length target: enough that the user can study it without opening any other file. Roughly 800-1500 words equivalent.

### Challenge holder body

```
# Coding Challenges — <count> problems × ~<min>min
## Solving Template (use on every problem)
[insert the 4-Stage Solving Template from SKILL.md]
```

The 4-stage template lives on the Challenge holder so the user sees it before opening any individual problem. Each problem page then references it.

### Individual problem body

```
# DN-PX — <problem name>
**Target time:** X min

## Problem
<problem statement>

## Input
<folder spec with target files + decoys, per Input Convention>

## Expected output
<sample I/O>

## Solving slots (apply 4-stage template)
```python
# 1. First working
```
```python
# 2. Edge cases handled
```
```python
# 3. Clean final
```

## Pre-Submit Ritual
- [ ] Empty set behavior?
- [ ] Aggregate in arithmetic → COALESCE?
- [ ] INNER vs LEFT JOIN — unmatched preserved?
- [ ] Boundary cases (first/last/single row)?
```

### Problem count sizing (per day)

For warm-up days, each day has 3 layers totaling ~2.5-3 hours:

| Layer | Purpose | Count × Time |
|---|---|---|
| Core | Teaching style, trade-offs explicit | 5-8 × 15-18 min |
| Extension | Reflection after passing each problem | 5 min thinking per problem |
| Sub-pattern | Variants exploring related techniques | 3 × 15 min |
| Cold problem | No hints, no trade-offs, exam simulation | 1 × 25-30 min |

For later (harder) days, sizing shifts as difficulty rises:

| Day type | Problem count | Time per problem |
|---|---|---|
| Easy (warm-up) | 5 core + 3 sub + 1 cold | 15-25 min each |
| Medium | 5 core + 1 cold | 18-30 min each |
| Hard | 3 core + 1 cold | 30-40 min each |
| Mock | 1 (the mock) | 90 min |
| Drill day (NULL, Pre-Submit reflex) | 10-20 | 5-10 min |
| Rest day | 0 | — |
