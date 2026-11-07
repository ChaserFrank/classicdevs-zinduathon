# Scoring

Every number on a skill card comes from a rule in `apps/analysis/services/` (pure Python, no
Django, no network). The AI model only writes the summary sentence and is checked against these
numbers. Thresholds live as named constants at the top of each module.

| Step | Module | What it does |
| --- | --- | --- |
| 1 Collect | `github.py` | 15 most recently pushed, non-fork, non-empty public repos → `Repo`/`Commit` dataclasses |
| 2 Detect | `skills.py`, `manifests.py` | Languages, frameworks/tools from manifests, practices from the file tree |
| 3 Confidence | `skills.py` | Evidence per repo and per skill → label |
| 4 Score | `scores.py` | Five sub-scores (0–20) → Signal Score (0–100) |
| 5 Flags | `flags.py` | Noise flags, one per repo at most |
| 6 Claims | `claims.py` | CV claims vs. evidence |
| 7 Tips | `tips.py` | Up to 3 concrete improvements |
| 8 Summary | `summary.py` | Three sentences; grounding check; template fallback |

## 1. Collecting evidence

Per repo: languages, the user's commits (up to 300), the total commit count (one request using the
`Link: rel="last"` page trick), stats for a **deterministic sample of 20** of the user's commits
(seeded by the repo's full name, so the same history always scores the same), the file tree,
manifests at the root or one directory down (max 5, skipping `node_modules/`, `vendor/`…), and the
README size. Forks and empty repos are dropped before anything is counted.

## 2. Detecting skills

| Source | Rule |
| --- | --- |
| Languages | GitHub's byte counts; a language under **5%** of a repo is ignored. Names map through the skill/alias tables ("Jupyter Notebook" → Python) |
| Manifests | `package.json` (deps, devDeps, peerDeps), `requirements.txt`, `pyproject.toml` (PEP 621, Poetry, dependency groups), `go.mod`, `pom.xml` → `DependencyMapping` rows. Express or NestJS also imply Node.js |
| Testing | Paths: `test/`, `tests/`, `__tests__/`, `test_*.py`, `*_test.py`, `*_test.go`, `*.test.js(x)/ts(x)`, `*.spec.js/ts` |
| CI/CD | A `.yml`/`.yaml` under `.github/workflows/` |
| Docker | `Dockerfile`, `docker-compose.yml/yaml`, `compose.yml/yaml` anywhere |

Admins extend detection by adding `DependencyMapping` or `SkillAlias` rows (Django admin now,
admin API in Phase 6). No deploy needed.

## 3. Confidence per skill

```
span(repo)      = 1.0 if ≥ 30 days between the user's first and last commit; 0.6 if ≥ 7; else 0.3
evidence(repo)  = min(1, user_commits / 20) × span(repo)
evidence(skill) = Σ evidence(repo) over repos showing the skill, rounded half-up to 2 dp
label           = Strong ≥ 2.0 · Moderate ≥ 0.8 · Emerging > 0 · Unverified = 0
```

Reading it: one sustained project (20+ commits over a month) gives 1.0, which is Moderate. Strong
needs the skill in at least two sustained projects.

## 4. Signal Score

Five integers, 0–20 each, rounded half-up and clamped; the score is their sum.

| Sub-score | Rule | Reason shown |
| --- | --- | --- |
| Consistency | `20 × min(1, distinct ISO weeks with commits in the last 365 days / 26)` | "Active in N of the last 52 weeks" |
| Iteration | Median sampled commit size (additions + deletions): ≤ 200 → 8, ≤ 500 → 5, else 2 (0 if nothing sampled). `+ 12 × repos with 10+ user commits / original repos`. `− 6 × repos where one commit holds > 50% of sampled added lines / original repos` | Median, sustained and dominated counts |
| Quality | +8 tests, +6 CI, +3 a README over 300 bytes, +3 a Dockerfile or `.env.example` (any original repo) | What is present and missing |
| Breadth | 4 per Strong skill + 2 per Moderate, max 20 | "N strong skills, M moderate" |
| Ownership | `20 × original repos where the user wrote ≥ 70% of the commits / original repos` | "Wrote most of the commits in N of M" |

## 5. Flags (prompts to check, never accusations)

At most one per repo, in this priority:

| Flag | Rule |
| --- | --- |
| `one_shot_dump` | ≥ 200 sampled added lines **and** one commit holds > 80% of them |
| `unexplained_bulk` | A sampled commit adding ≥ 2,000 lines with fewer than 3 of the user's commits after it |
| `tutorial_clone` | Name matches todo, calculator, weather, tic-tac-toe, hello-world, `<brand>-clone`… **and** fewer than 5 user commits |
| `unverified_claim` | A claimed skill with no evidence (not tied to a repo) |

## 6. Claims

Claimed text is normalised through skill names and aliases ("reactjs" → React). Verified = Strong
or Moderate; Partly = Emerging; Unverified = not detected (or detected with zero evidence).

## 7. Tips

Up to three, ordered by the weakest related sub-score: add tests/CI/README to the busiest repo
missing them, commit in smaller steps (dump flags), commit regularly (consistency < 15), build an
original project (ownership < 10), extend a tutorial project, publish something using an
unverified claim.

## 8. Summary

The model sees only: skills with labels and evidence, sub-scores with reasons, flags, and the repo
count. It may not name a catalogue skill we didn't detect (names under 3 characters such as "Go"
are skipped because they collide with ordinary words) or use a number that isn't in that JSON.
Otherwise, and when there is no key, a timeout or a refusal, a deterministic three-sentence template
is used. `summary_source` records which.

## Worked example (fixture `amina-dev`, run on 2026-11-07)

| Repo | User commits | Span | Evidence | Shows |
| --- | --- | --- | --- | --- |
| shop-app | 44 weekly over 10 months (48 total) | 1.0 | 1.0 | TypeScript, CSS, React, Next.js, Tailwind CSS, Testing, CI/CD, Docker |
| duka-api | 24 every 10 days (30 total) | 1.0 | 1.0 | Python, Django, DRF, PostgreSQL, Testing |
| matatu-routes | 3 in two days, first adds 2,600 lines | 0.3 | 0.15 × 0.3 = 0.045 → 0.05 | JavaScript, Express, Node.js |

- Testing appears in two sustained repos: 1.0 + 1.0 = **2.0, Strong**. Everything else is Moderate
  (1.0) or Emerging (0.05).
- Consistency: 44 active weeks ≥ 26 → **20**.
- Iteration: median sampled commit 100 lines → 8; 2 of 3 repos have 10+ commits → +8; 1 of 3
  repos is dominated by one commit → −2; total **14**.
- Quality: tests, CI, README > 300 bytes, Dockerfile → **20**.
- Breadth: 1 Strong (4) + 11 Moderate (22) = 26 → capped at **20**.
- Ownership: the user wrote ≥ 70% of commits in 3 of 3 → **20**.
- **Signal Score 94.** Flag: `one_shot_dump` on matatu-routes (99% of sampled lines in one
  commit). Tip: "Commit in smaller steps: 1 repo arrived mostly in one commit".

**Calibration note:** breadth saturates quickly because every framework in a well-built repo
counts. If judges find scores too generous, capping the dependency-derived skills counted per repo
is a one-line change in `scores.breadth`. Any change goes in `../TESTING_LOG.md`.

## Changing a threshold safely

1. Change the constant in its module (e.g. `STRONG` in `skills.py`).
2. Update the table above and add a line to `../TESTING_LOG.md` saying why.
3. Run `make test`: the boundary tests in `tests/analysis/test_rules_*.py` pin every threshold, so
   update them deliberately.
4. Existing analyses keep their stored numbers; re-run with `force=true` to rescore.
