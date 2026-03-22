import streamlit as st
from analyzer import analyze_repo, format_difficulty_badge

st.set_page_config(
    page_title="GitHub Repository Intelligence Analyzer",
    page_icon="🔍",
    layout="wide"
)

st.title("GitHub Repository Intelligence Analyzer")
st.markdown("Analyze GitHub repositories for activity, complexity, and learning difficulty.")

# ── Sidebar: token input ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("Configuration")
    token = st.text_input(
        "GitHub Personal Access Token",
        type="password",
        help="Generate at github.com → Settings → Developer settings → Personal access tokens"
    )
    st.markdown("---")
    st.markdown("**How scoring works**")
    st.markdown("""
- **Activity score** (0–100): weighted sum of recent commits, open issues, PRs, and contributors
- **Complexity score** (0–100): based on language count, file count estimate, and presence of dependency files
- **Difficulty**: derived from both scores — Beginner / Intermediate / Advanced
""")

# ── Main input ────────────────────────────────────────────────────────────────
st.subheader("Enter Repository URLs")
raw_input = st.text_area(
    "One URL per line",
    placeholder="https://github.com/torvalds/linux\nhttps://github.com/facebook/react\nhttps://github.com/pallets/flask",
    height=160
)

analyze_btn = st.button("Analyze Repositories", type="primary", use_container_width=True)

# ── Run analysis ──────────────────────────────────────────────────────────────
if analyze_btn:
    if not token:
        st.error("Please enter your GitHub Personal Access Token in the sidebar.")
        st.stop()

    urls = [u.strip() for u in raw_input.strip().splitlines() if u.strip()]
    if not urls:
        st.warning("Please enter at least one repository URL.")
        st.stop()

    st.markdown("---")
    st.subheader("Analysis Results")

    for url in urls:
        with st.spinner(f"Analyzing {url} ..."):
            result = analyze_repo(url, token)

        if "error" in result:
            st.error(f"**{url}** — {result['error']}")
            continue

        difficulty_color = {
            "Beginner":     "green",
            "Intermediate": "orange",
            "Advanced":     "red",
        }.get(result["difficulty"], "gray")

        with st.container(border=True):
            col_title, col_badge = st.columns([3, 1])
            with col_title:
                st.markdown(f"### [{result['full_name']}]({result['url']})")
                st.caption(result["description"] or "No description available.")
            with col_badge:
                st.markdown(
                    f"<div style='text-align:right; padding-top:8px'>"
                    f"<span style='background:{difficulty_color};color:white;"
                    f"padding:4px 14px;border-radius:12px;font-weight:600;font-size:14px'>"
                    f"{result['difficulty']}</span></div>",
                    unsafe_allow_html=True
                )

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Stars",        f"{result['stars']:,}")
            m2.metric("Forks",        f"{result['forks']:,}")
            m3.metric("Contributors", result["contributors"])
            m4.metric("Open Issues",  result["open_issues"])
            m5.metric("Activity",     f"{result['activity_score']}/100")
            m6.metric("Complexity",   f"{result['complexity_score']}/100")

            with st.expander("Score breakdown & details"):
                left, right = st.columns(2)

                with left:
                    st.markdown("**Activity score breakdown**")
                    st.markdown(f"- Recent commits (last 30 days): **{result['breakdown']['commits']}** pts")
                    st.markdown(f"- Open issues: **{result['breakdown']['issues']}** pts")
                    st.markdown(f"- Open pull requests: **{result['breakdown']['prs']}** pts")
                    st.markdown(f"- Contributor count: **{result['breakdown']['contributors']}** pts")
                    st.markdown(f"- Stars momentum: **{result['breakdown']['stars']}** pts")
                    st.markdown(f"**Total activity score: {result['activity_score']}/100**")

                with right:
                    st.markdown("**Complexity score breakdown**")
                    st.markdown(f"- Language count: **{result['breakdown']['lang_count']}** language(s)")
                    st.markdown(f"- Language diversity pts: **{result['breakdown']['lang_pts']}** pts")
                    st.markdown(f"- Size estimate pts: **{result['breakdown']['size_pts']}** pts")
                    st.markdown(f"- Dependency files found: **{result['breakdown']['dep_pts']}** pts")
                    st.markdown(f"**Total complexity score: {result['complexity_score']}/100**")

                st.markdown("**Languages detected**")
                st.write(", ".join(result["languages"]) if result["languages"] else "Not available")

                st.markdown("**Difficulty classification logic**")
                st.info(result["difficulty_reason"])

        st.markdown("")  # spacer between cards

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("C2SI Pre-GSoC Task 2026 — GitHub Repository Intelligence Analyzer")
