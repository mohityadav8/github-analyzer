"""
GitHub Repository Intelligence Analyzer — Core Logic
=====================================================

SCORING FORMULAS
----------------

Activity Score (0–100)
  Measures how actively a repository is being developed and maintained.

  Formula:
    commit_pts      = min(recent_commits / 50 * 40, 40)   # 40 pts max — 50 commits in last 30d = full
    issue_pts       = min(open_issues   / 20 * 15, 15)    # 15 pts max — 20 open issues = full
    pr_pts          = min(open_prs      / 10 * 20, 20)    # 20 pts max — 10 open PRs = full
    contributor_pts = min(contributors  / 10 * 15, 15)    # 15 pts max — 10+ contributors = full
    star_pts        = min(log10(stars+1) / log10(10001) * 10, 10) # 10 pts max — log scale

    activity_score = commit_pts + issue_pts + pr_pts + contributor_pts + star_pts

  Rationale: Commits are weighted highest (40 pts) because they are the
  strongest signal of active development. PRs (20 pts) indicate collaborative
  activity. Issues (15 pts) and contributors (15 pts) show community engagement.
  Stars use a logarithmic scale to prevent large popular repos from dominating.

Complexity Score (0–100)
  Estimates how technically complex the codebase is.

  Formula:
    lang_pts = min(language_count * 10, 40)        # 40 pts max — 4+ languages = full
    size_pts = min(repo_size_kb / 5000 * 30, 30)   # 30 pts max — 5 MB codebase = full
    dep_pts  = dependency_files_count * 10          # 10 pts per dep file (max 30)
    dep_pts  = min(dep_pts, 30)

    complexity_score = lang_pts + size_pts + dep_pts

  Rationale: Language diversity (40 pts) strongly indicates complexity.
  Codebase size (30 pts) correlates with lines of code and abstraction depth.
  Dependency files (30 pts) — presence of package.json, requirements.txt,
  Cargo.toml, pom.xml, etc. indicates non-trivial build and dependency management.

Difficulty Classification
  Derived from the combined weighted average of both scores.

  combined = activity_score * 0.4 + complexity_score * 0.6

  Beginner:     combined < 30
  Intermediate: 30 <= combined < 60
  Advanced:     combined >= 60

  Rationale: Complexity is weighted more (0.6) than activity (0.4) because a
  highly complex but low-activity repo is still hard to learn. Activity weight
  ensures dormant simple repos are not over-scored.

EDGE CASE HANDLING
------------------
- Missing commit data: commit_pts defaults to 0
- Empty repositories (0 stars, 0 commits): all scores default to 0, classified Beginner
- Private or non-existent repos: returns an error message
- Rate limit exceeded: returns a descriptive error with retry advice
- Missing language data: lang_pts = 0
"""

import requests
import math
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse


DEPENDENCY_FILES = {
    "requirements.txt", "Pipfile", "setup.py", "pyproject.toml",  # Python
    "package.json", "yarn.lock", "package-lock.json",              # JS/TS
    "Cargo.toml",                                                   # Rust
    "pom.xml", "build.gradle",                                     # Java
    "go.mod",                                                       # Go
    "Gemfile",                                                      # Ruby
    "composer.json",                                                # PHP
    "*.csproj", "*.sln",                                           # C#
    "CMakeLists.txt",                                              # C/C++
}


def _headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }


def _parse_repo(url: str):
    """Extract owner/repo from a GitHub URL. Returns (owner, repo) or raises ValueError."""
    url = url.strip().rstrip("/")
    # Accept both https://github.com/owner/repo and owner/repo shorthand
    if url.startswith("http"):
        parts = urlparse(url).path.strip("/").split("/")
    else:
        parts = url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse repository from '{url}'. Use format: https://github.com/owner/repo")
    return parts[0], parts[1]


def _get(url: str, token: str) -> dict:
    """Make a GET request and return parsed JSON or raise on error."""
    resp = requests.get(url, headers=_headers(token), timeout=15)
    if resp.status_code == 401:
        raise PermissionError("Invalid GitHub token. Please check your token and try again.")
    if resp.status_code == 403:
        reset = resp.headers.get("X-RateLimit-Reset")
        if reset:
            reset_time = datetime.fromtimestamp(int(reset), tz=timezone.utc)
            wait = max(0, int((reset_time - datetime.now(timezone.utc)).total_seconds() // 60))
            raise RuntimeError(f"GitHub API rate limit exceeded. Resets in ~{wait} minutes.")
        raise RuntimeError("GitHub API rate limit exceeded. Please wait and try again.")
    if resp.status_code == 404:
        raise FileNotFoundError("Repository not found. Check the URL or make sure it is public.")
    resp.raise_for_status()
    return resp.json()


def _compute_activity_score(recent_commits, open_issues, open_prs, contributors, stars):
    """
    Activity Score (0–100)
    See module docstring for full formula explanation.
    """
    commit_pts      = min(recent_commits / 50 * 40, 40)
    issue_pts       = min(open_issues    / 20 * 15, 15)
    pr_pts          = min(open_prs       / 10 * 20, 20)
    contributor_pts = min(contributors   / 10 * 15, 15)
    star_pts        = min(math.log10(stars + 1) / math.log10(10001) * 10, 10)

    total = commit_pts + issue_pts + pr_pts + contributor_pts + star_pts

    return round(total), {
        "commits":      round(commit_pts, 1),
        "issues":       round(issue_pts, 1),
        "prs":          round(pr_pts, 1),
        "contributors": round(contributor_pts, 1),
        "stars":        round(star_pts, 1),
    }


def _compute_complexity_score(language_count, repo_size_kb, dep_file_count):
    """
    Complexity Score (0–100)
    See module docstring for full formula explanation.
    """
    lang_pts = min(language_count * 10, 40)
    size_pts = min(repo_size_kb / 5000 * 30, 30)
    dep_pts  = min(dep_file_count * 10, 30)

    total = lang_pts + size_pts + dep_pts

    return round(total), {
        "lang_count": language_count,
        "lang_pts":   round(lang_pts, 1),
        "size_pts":   round(size_pts, 1),
        "dep_pts":    round(dep_pts, 1),
    }


def _classify_difficulty(activity_score, complexity_score):
    """
    Difficulty Classification
    See module docstring for full logic explanation.
    """
    combined = activity_score * 0.4 + complexity_score * 0.6

    if combined < 30:
        level  = "Beginner"
        reason = (
            f"Combined score {combined:.1f} < 30. "
            "The repository has limited activity and low technical complexity, "
            "making it accessible for newcomers."
        )
    elif combined < 60:
        level  = "Intermediate"
        reason = (
            f"Combined score {combined:.1f} is between 30–60. "
            "The repository has moderate activity and/or complexity, "
            "requiring some prior programming experience."
        )
    else:
        level  = "Advanced"
        reason = (
            f"Combined score {combined:.1f} >= 60. "
            "The repository is highly active and/or technically complex, "
            "best suited for experienced developers."
        )

    return level, reason


def analyze_repo(url: str, token: str) -> dict:
    """
    Main entry point. Fetches GitHub data for a repo URL and returns
    a structured result dict with all scores, breakdowns, and metadata.
    """
    try:
        owner, repo = _parse_repo(url)
    except ValueError as e:
        return {"error": str(e)}

    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    # ── 1. Core repo metadata ──────────────────────────────────────────────
    try:
        meta = _get(api_base, token)
    except (PermissionError, RuntimeError, FileNotFoundError) as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Unexpected error fetching repo: {e}"}

    stars      = meta.get("stargazers_count", 0)
    forks      = meta.get("forks_count", 0)
    open_issues = meta.get("open_issues_count", 0)  # GitHub includes PRs in this count
    repo_size_kb = meta.get("size", 0)
    description = meta.get("description", "")

    # ── 2. Open pull requests (separate from issues) ───────────────────────
    try:
        prs = _get(f"{api_base}/pulls?state=open&per_page=100", token)
        open_prs = len(prs) if isinstance(prs, list) else 0
        # Subtract PRs from issues count so they don't double-count
        open_issues_only = max(0, open_issues - open_prs)
    except Exception:
        open_prs = 0
        open_issues_only = open_issues

    # ── 3. Recent commit count (last 30 days) ──────────────────────────────
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        commits = _get(f"{api_base}/commits?since={since}&per_page=100", token)
        recent_commits = len(commits) if isinstance(commits, list) else 0
    except Exception:
        recent_commits = 0

    # ── 4. Contributors ────────────────────────────────────────────────────
    try:
        contributors_data = _get(f"{api_base}/contributors?per_page=100&anon=true", token)
        contributor_count = len(contributors_data) if isinstance(contributors_data, list) else 0
    except Exception:
        contributor_count = 0

    # ── 5. Languages ───────────────────────────────────────────────────────
    try:
        lang_data = _get(f"{api_base}/languages", token)
        languages = list(lang_data.keys()) if isinstance(lang_data, dict) else []
    except Exception:
        languages = []

    # ── 6. Dependency files in root directory ─────────────────────────────
    dep_file_count = 0
    try:
        root_contents = _get(f"{api_base}/contents", token)
        if isinstance(root_contents, list):
            root_names = {item["name"].lower() for item in root_contents}
            dep_keywords = {
                "requirements.txt", "pipfile", "setup.py", "pyproject.toml",
                "package.json", "cargo.toml", "pom.xml", "build.gradle",
                "go.mod", "gemfile", "composer.json",
            }
            dep_file_count = len(root_names & dep_keywords)
    except Exception:
        dep_file_count = 0

    # ── 7. Compute scores ──────────────────────────────────────────────────
    activity_score, activity_breakdown = _compute_activity_score(
        recent_commits, open_issues_only, open_prs, contributor_count, stars
    )
    complexity_score, complexity_breakdown = _compute_complexity_score(
        len(languages), repo_size_kb, dep_file_count
    )
    difficulty, difficulty_reason = _classify_difficulty(activity_score, complexity_score)

    breakdown = {**activity_breakdown, **complexity_breakdown}

    return {
        "full_name":        meta.get("full_name", f"{owner}/{repo}"),
        "url":              meta.get("html_url", url),
        "description":      description,
        "stars":            stars,
        "forks":            forks,
        "open_issues":      open_issues_only,
        "open_prs":         open_prs,
        "contributors":     contributor_count,
        "recent_commits":   recent_commits,
        "languages":        languages,
        "repo_size_kb":     repo_size_kb,
        "activity_score":   activity_score,
        "complexity_score": complexity_score,
        "difficulty":       difficulty,
        "difficulty_reason": difficulty_reason,
        "breakdown":        breakdown,
    }


def format_difficulty_badge(difficulty: str) -> str:
    colors = {"Beginner": "green", "Intermediate": "orange", "Advanced": "red"}
    color = colors.get(difficulty, "gray")
    return f":{color}[{difficulty}]"
