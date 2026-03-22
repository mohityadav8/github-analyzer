# GitHub Repository Intelligence Analyzer

**C2SI Pre-GSoC Task 2026 — Task 2**

A tool that analyzes multiple GitHub repositories and generates insights about their activity, complexity, and learning difficulty.

## Live Demo

🌐 **[Live App →](https://your-app.streamlit.app)** *(replace with your deployed URL)*

## Features

- Accepts a list of GitHub repository URLs as input
- Fetches real data via the GitHub REST API (stars, forks, contributors, languages, commits, PRs)
- Calculates a custom **Activity Score** (0–100)
- Calculates a custom **Complexity Score** (0–100)
- Classifies each repo as **Beginner**, **Intermediate**, or **Advanced**
- Shows a full per-score breakdown for transparency
- Handles edge cases: missing data, empty repos, rate limits, invalid URLs

---

## Setup & Running Locally

**Prerequisites:** Python 3.9+

```bash
# 1. Clone or download this repository
git clone https://github.com/YOUR_USERNAME/github-analyzer
cd github-analyzer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app opens at **http://localhost:8501**

You will be prompted for a GitHub Personal Access Token in the sidebar. Generate one at:
`github.com → Settings → Developer settings → Personal access tokens → Tokens (classic)`
No scopes are required — public data is freely accessible.

---

## Scoring Formulas & Design Decisions

### Activity Score (0–100)

Measures how actively a repository is being developed and maintained.

| Component | Formula | Max pts | Rationale |
|---|---|---|---|
| Recent commits (last 30 days) | `min(commits / 50 × 40, 40)` | 40 | Strongest signal of active development |
| Open pull requests | `min(prs / 10 × 20, 20)` | 20 | Indicates collaborative activity |
| Open issues | `min(issues / 20 × 15, 15)` | 15 | Shows community engagement |
| Contributor count | `min(contributors / 10 × 15, 15)` | 15 | Multi-contributor = healthy project |
| Stars (log scale) | `min(log10(stars+1) / log10(10001) × 10, 10)` | 10 | Logarithmic to prevent large repos dominating |

**Why commits are weighted highest (40 pts):** A repo with recent commits is actively maintained. A repo with 10,000 stars but no commits in 2 years is less valuable to contribute to.

**Why stars use a log scale:** The difference between 1 and 100 stars is meaningful. The difference between 50,000 and 100,000 is less so. A log scale compresses the upper end fairly.

### Complexity Score (0–100)

Estimates how technically complex the codebase is to understand and contribute to.

| Component | Formula | Max pts | Rationale |
|---|---|---|---|
| Language count | `min(language_count × 10, 40)` | 40 | Multi-language codebases are harder to navigate |
| Repository size | `min(size_kb / 5000 × 30, 30)` | 30 | Large repos have more code to understand |
| Dependency files | `min(dep_file_count × 10, 30)` | 30 | Complex build systems increase onboarding cost |

**Dependency files checked:** `requirements.txt`, `package.json`, `Cargo.toml`, `pom.xml`, `build.gradle`, `go.mod`, `Gemfile`, `composer.json`, `pyproject.toml`, `Pipfile`, `setup.py`

### Difficulty Classification

The combined score uses a weighted average, giving more weight to complexity:

```
combined = activity_score × 0.4 + complexity_score × 0.6
```

| Range | Classification |
|---|---|
| combined < 30 | Beginner |
| 30 ≤ combined < 60 | Intermediate |
| combined ≥ 60 | Advanced |

**Why complexity is weighted more (0.6):** A highly complex but low-activity repo is still technically hard to learn. A simple but very active repo may be easier to jump into despite its activity level.

---

## Edge Case Handling

| Scenario | Handling |
|---|---|
| Missing commit data | `recent_commits` defaults to 0 |
| Empty repository | All scores default to 0, classified Beginner |
| Repository not found (404) | Returns clear error message |
| Invalid GitHub token (401) | Returns descriptive auth error |
| Rate limit exceeded (403) | Returns error with minutes until reset |
| Invalid URL format | Returns parse error with correct format hint |
| No languages detected | `lang_pts = 0`, rest of score still computed |
| Private repository | Returns 404-style error (not accessible) |

---

## Rate Limit Strategy

- Uses authenticated requests (token) for 5,000 requests/hour vs 60 unauthenticated
- Makes at most 6 API calls per repository (meta, PRs, commits, contributors, languages, contents)
- For 5 repositories: ~30 calls total — well within limits
- Rate limit headers (`X-RateLimit-Remaining`, `X-RateLimit-Reset`) are checked on every 403 response and reported to the user

---

## Sample Outputs

See the [sample outputs](./sample_outputs/) folder for generated reports on 5 repositories:

1. `torvalds/linux` — Advanced
2. `pallets/flask` — Intermediate
3. `sindresorhus/awesome` — Beginner
4. `facebook/react` — Advanced
5. `requests/requests` — Intermediate

---

## Assumptions & Limitations

- **Commit count** uses the last 30 days only, fetching up to 100 commits per page. Repos with >100 commits/month will be capped (slightly underscores very active repos).
- **Contributor count** fetches up to 100 contributors per page. Repos with >100 contributors receive the same maximum points.
- **Repository size** is the GitHub-reported compressed size in KB — not a raw line count. This is an approximation.
- **Dependency files** only checks the root directory — monorepos with nested packages may be under-scored on complexity.
- **Private repositories** cannot be analyzed without a token with `repo` scope.

---

## Technology Stack

| Component | Technology |
|---|---|
| UI framework | Streamlit |
| GitHub API | GitHub REST API v3 (via `requests`) |
| Language | Python 3.9+ |
| Deployment | Streamlit Cloud |
