# DE Interview Prep — Claude Code Skill

A Claude Code skill that coaches you through Data Engineer coding test preparation (CodeSignal, HackerRank, etc.).

## What It Does

- **Code review** with a DE-specific bug checklist (truthiness, dedup, sorting, NULL handling)
- **Pattern teaching** with step-by-step traces and signal-to-pattern mapping
- **Mock exam generation** matching real assessment format (2 SQL + 2 Python + 1 Debug)
- **Gap analysis** across completed problems to identify weak areas
- **Fatigue detection** — suggests breaks when error patterns indicate tiredness

## Assessment Format Covered

| Question | Type | Difficulty | Time |
|---|---|---|---|
| Q1 | SQL | Easy | 10 min |
| Q2 | SQL | Medium | 15 min |
| Q3 | Python | Medium | 15 min |
| Q4 | Python | Hard | 25 min |
| Q5 | Debug | Medium | 15 min |

## Files

```
SKILL.md              — Main skill instructions and workflows
patterns.md           — Pattern reference (Sliding Window, Prefix Sum, SQL Signals, etc.)
debug-checklist.md    — Top 5 pipeline bug patterns + debug problem template
mock-exam-guide.md    — Mock exam design, scoring, and time management guide
```

## Installation

Copy the skill into your Claude Code skills directory:

```bash
# Project-level (this repo only)
cp -r . /path/to/your/project/.claude/skills/de-interview-prep/

# User-level (all projects)
cp -r . ~/.claude/skills/de-interview-prep/
```

Then start a new Claude Code session and invoke with `/de-interview-prep`.

## Usage Examples

```
/de-interview-prep Create a mock exam for me
/de-interview-prep Review my SQL solution
/de-interview-prep Teach me the Sliding Window pattern
/de-interview-prep Analyze my weaknesses across all problems
```

## Patterns Covered

**Python:** Sliding Window, Prefix Sum + HashMap, Two Pointers, 3Sum, Binary Search, Counter/HashMap

**SQL:** JOIN decisions, Window Functions (RANK/DENSE_RANK/ROW_NUMBER), Gap-and-Island, GROUP BY + HAVING, CTE, CASE WHEN, GROUP_CONCAT

**Debug:** Status filter, dedup, truthiness vs None, output sorting, division by zero

## License

MIT
