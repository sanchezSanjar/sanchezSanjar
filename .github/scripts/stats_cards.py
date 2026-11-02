"""Draws the GitHub stats and top-languages cards for the profile README.

Run by the "Profile images" workflow with the workflow's own GITHUB_TOKEN, so no personal token
is needed. Languages come from the public repositories only (the token cannot see private ones);
the contribution count includes private work when the profile shows private contributions.

    python .github/scripts/stats_cards.py <user> <output folder>
"""
import json
import os
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
BG, TITLE, TEXT, VALUE, MUTED = "#0D1117", "#3A86C8", "#C9D1D9", "#FFFFFF", "#8B949E"
FONT = "font-family:'Segoe UI',Ubuntu,'Helvetica Neue',sans-serif"
SKIP_LANGUAGES = {"Jupyter Notebook"}  # notebook files are mostly saved outputs, not code
COLORS = {
    "TypeScript": "#3178C6", "JavaScript": "#F1E05A", "Python": "#F4A259", "HTML": "#E34C26",
    "CSS": "#563D7C", "SCSS": "#C6538C", "C#": "#178600", "Dockerfile": "#384D54", "Shell": "#89E051",
    "EJS": "#A91E50", "PowerShell": "#012456", "Batchfile": "#C1F12E", "Java": "#B07219", "Go": "#00ADD8",
}


def get(url: str, data: dict | None = None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats-cards"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    body = json.dumps(data).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=30) as response:
        return json.loads(response.read())


def contributions(user: str) -> dict | None:
    """Contribution numbers from the GraphQL API (needs a token, which the workflow provides)."""
    if not TOKEN:
        return None
    query = """query($login: String!) { user(login: $login) {
        contributionsCollection { totalCommitContributions contributionCalendar { totalContributions } }
        pullRequests { totalCount } issues { totalCount } } }"""
    try:
        result = get(f"{API}/graphql", {"query": query, "variables": {"login": user}})
        node = result["data"]["user"]
        collection = node["contributionsCollection"]
        return {"contributions": collection["contributionCalendar"]["totalContributions"],
                "commits": collection["totalCommitContributions"],
                "prs": node["pullRequests"]["totalCount"], "issues": node["issues"]["totalCount"]}
    except Exception as error:  # the card then shows stars, repositories and followers only
        print(f"Contribution numbers not available: {error}", file=sys.stderr)
        return None


def collect(user: str) -> dict:
    profile = get(f"{API}/users/{user}")
    repos = [r for r in get(f"{API}/users/{user}/repos?type=owner&per_page=100") if not r["fork"]]
    languages: dict[str, int] = {}
    for repo in repos:
        for name, size in get(repo["languages_url"]).items():
            if name not in SKIP_LANGUAGES:
                languages[name] = languages.get(name, 0) + size
    return {"public_repos": profile["public_repos"], "followers": profile["followers"],
            "stars": sum(r["stargazers_count"] for r in repos), "languages": languages,
            "activity": contributions(user)}


def card(width: int, height: int, title: str, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<rect width="{width}" height="{height}" rx="10" fill="{BG}"/>'
            f'<text x="25" y="38" style="{FONT};font-size:18px;font-weight:600" fill="{TITLE}">{escape(title)}</text>'
            f"{body}</svg>")


def stats_card(user: str, data: dict) -> str:
    rows = [("Total stars", data["stars"])]
    if data["activity"]:
        rows += [("Contributions (last year)", data["activity"]["contributions"]),
                 ("Commits (last year)", data["activity"]["commits"]),
                 ("Pull requests", data["activity"]["prs"])]
    rows += [("Public repositories", data["public_repos"]), ("Followers", data["followers"])]
    body = ""
    for i, (label, value) in enumerate(rows):
        y = 74 + i * 26
        body += (f'<circle cx="31" cy="{y - 5}" r="4" fill="{TITLE}"/>'
                 f'<text x="45" y="{y}" style="{FONT};font-size:14px" fill="{TEXT}">{escape(label)}:</text>'
                 f'<text x="300" y="{y}" style="{FONT};font-size:14px;font-weight:700" fill="{VALUE}">{value:,}</text>')
    return card(420, 74 + len(rows) * 26, f"{user}'s GitHub stats", body)


def languages_card(data: dict, top: int = 6) -> str:
    ranked = sorted(data["languages"].items(), key=lambda item: -item[1])[:top]
    total = sum(size for _, size in ranked) or 1
    body, x = '<clipPath id="bar"><rect x="25" y="55" width="310" height="9" rx="4.5"/></clipPath><g clip-path="url(#bar)">', 25.0
    for name, size in ranked:
        width = 310 * size / total
        body += f'<rect x="{x:.1f}" y="55" width="{width:.1f}" height="9" fill="{COLORS.get(name, MUTED)}"/>'
        x += width
    body += "</g>"
    for i, (name, size) in enumerate(ranked):
        col, row = i % 2, i // 2
        cx, cy = 30 + col * 160, 92 + row * 24
        body += (f'<circle cx="{cx}" cy="{cy - 4}" r="5" fill="{COLORS.get(name, MUTED)}"/>'
                 f'<text x="{cx + 12}" y="{cy}" style="{FONT};font-size:13px" fill="{TEXT}">{escape(name)} '
                 f'<tspan fill="{MUTED}">{100 * size / total:.1f}%</tspan></text>')
    height = 92 + ((len(ranked) + 1) // 2) * 24
    return card(360, height, "Top languages (public repos)", body)


def main() -> None:
    user, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    data = collect(user)
    (out / "github-stats.svg").write_text(stats_card(user, data), encoding="utf-8")
    (out / "top-languages.svg").write_text(languages_card(data), encoding="utf-8")
    print(f"stars {data['stars']}, languages {len(data['languages'])}, activity {data['activity']}")


if __name__ == "__main__":
    main()
