# Contributing

## Goal

This repository exists to develop and validate AgentForge with a focus on:

- spec-configurable agents;
- practical use of local and on-premise models;
- memory, history, and controlled context policies;
- guided creation of agents and tools;
- efficacy and operational predictability testing.

The project priority is incremental, verifiable, and well-documented evolution.

## Principles

- Make small, testable changes.
- Commits must represent real changes.
- Avoid mixing refactor, feature, test, and documentation in the same commit when it harms readability.
- Keep the working tree clean between relevant tasks.
- Every functional change must be validated before committing, at minimum with a targeted test or explicit manual verification.

## Commit convention

Use Conventional Commits in a simple form:

- `feat:` new functionality.
- `fix:` bug fix.
- `refactor:` structural change without altering expected behavior.
- `test:` creating or adjusting tests.
- `docs:` documentation.
- `chore:` maintenance, cleanup, auxiliary files, and operational tasks.

Examples:

- `feat(runtime): add multi-turn conversation history`
- `feat(memory): add summarize policy for bounded history`
- `feat(wizard): support complex agents and rich tools`
- `test(memory): cover summarize accumulation behavior`
- `docs(repo): add operational manifesto`
- `chore: remove accidental file from repository root`

## Commit rule

Commit whenever there is a real, coherent, and minimally validated change.

Situations where a commit should happen:

- a small feature has been completed;
- a fix has been validated;
- a relevant block of tests has been added or adjusted;
- an important documentation update has been completed;
- a relevant operational cleanup has been finalized.

Avoid:

- accumulating many hours of useful work without committing;
- leaving several different changes mixed together unnecessarily;
- ending the day with an important change not versioned.

## Workflow

Recommended sequence for normal changes:

1. Understand the problem and define a short scope.
2. Change only the necessary files.
3. Run targeted tests or objective manual validation.
4. Review `git diff` and `git status`.
5. Commit with a clear message.
6. Only then start the next change.

Useful commands:

```bash
git status
git diff
git add -A
git commit -m "feat(...): descrição"
```

When necessary, use `git add -p` to separate changes by intent.

## Clean tree

Before starting a new relevant task:

- check `git status`;
- confirm the tree is clean, or understand exactly what is pending.

Before ending a work session:

- run `git status`;
- consciously decide whether a commit is still needed.

## Minimum validation

Every change must have some level of validation proportional to its risk:

- small text change: manual review;
- generation/config change: targeted test;
- runtime/provider/memory/wizard change: relevant automated tests;
- agent behavior change: explicit manual test and, when possible, automated test.

Whenever applicable, record in the commit or local PR which commands were used for validation.

## Agent roles

Recommended operational use in this repository:

- **Perplexity**: orchestration, planning, final validation, and defining the next best step.
- **Claude Code**: more complex implementation, structural changes, and difficult architectural decisions.
- **OpenCode**: smaller tasks, local adjustments, operational documentation, UX improvements, and simple refactors.
- **Gemini CLI**: review, documentation, validation, gap criticism, and improvement suggestions.

The human remains the final orchestrator and is responsible for:

- approving direction;
- executing sensitive commands;
- validating priorities;
- deciding what goes into the repository.

## Change scope

Prefer small, iterative changes.

Good practice:

- first get the minimal infrastructure working;
- then cover with tests;
- then improve UX, docs, and refinements.

Avoid large refactors outside the critical path unless there is a clear gain in simplicity, security, or testability.

## Living documentation

Whenever a change alters how the project is used, evaluate whether it is also necessary to update:

- `README.md`
- `ROADMAP.md`
- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `opencode.md`
- manifestos and operational documents

Outdated documentation leads to context loss and degrades agent usage.

## Long-term goal

Build an agent framework that is:

- usable;
- testable;
- predictable;
- economical;
- useful as both a lab and a portfolio.

Every contribution should move the repository closer to that goal.
