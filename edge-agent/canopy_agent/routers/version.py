import os

import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/api/version", tags=["version"])

GITHUB_REPO = "hashking710/Canopy"
CHECK_TIMEOUT_SECONDS = 8.0


def _current_sha() -> str | None:
    # Baked into the image at build time — see edge-agent/Dockerfile's CANOPY_GIT_SHA
    # arg, docker-compose.yml's build.args, and deploy/install.sh (which exports it
    # from `git rev-parse HEAD` before building). Empty/"unknown" for a manual
    # `docker build` with no git context, or a tarball install with no .git dir.
    sha = os.environ.get("CANOPY_GIT_SHA", "").strip()
    if not sha or sha == "unknown":
        return None
    return sha


@router.get("")
def get_version() -> dict:
    """Instant, no network call — what's actually baked into this running image."""
    sha = _current_sha()
    return {"sha": sha, "short_sha": sha[:7] if sha else None, "repo": GITHUB_REPO}


async def _compare_to_main(sha: str, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Split out from the route for testability — `transport` lets tests inject an
    httpx.MockTransport instead of hitting the real network, same pattern as
    canopy_license.checkin.checkin()."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/compare/{sha}...main"
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_SECONDS, transport=transport) as client:
            resp = await client.get(url, headers={"Accept": "application/vnd.github+json"})
    except httpx.HTTPError as exc:
        return {"checked": False, "reason": f"couldn't reach GitHub: {exc}"}

    if resp.status_code == 404:
        return {
            "checked": False,
            "reason": "GitHub doesn't recognize this build's commit — can't compare (a local/dev build, or the repo's history changed)",
        }
    if resp.status_code != 200:
        return {"checked": False, "reason": f"GitHub returned HTTP {resp.status_code}"}

    body = resp.json()
    commits_behind = body.get("ahead_by", 0)  # "ahead" from this build's commit toward main's tip
    commits = body.get("commits") or []
    latest_sha = commits[-1]["sha"] if commits else sha
    return {
        "checked": True,
        "up_to_date": commits_behind == 0,
        "commits_behind": commits_behind,
        "latest_sha": latest_sha,
        "latest_short_sha": latest_sha[:7],
        "compare_url": f"https://github.com/{GITHUB_REPO}/compare/{sha}...main",
    }


@router.get("/check")
async def check_for_updates() -> dict:
    """
    Manual, on-demand only (see Settings.tsx's "check for updates" button) — never
    scheduled/automatic. Compares this build's baked-in commit against the tip of
    `main` via GitHub's compare API, which hands back exactly the "how many commits
    behind" count in one call (`ahead_by`, from base=this build's commit to
    head=main) rather than needing this to page through commit history itself.
    Actually applying an update is a separate, manual, host-level step (re-run
    `deploy/install.sh --upgrade`, or `git pull && docker compose up -d --build`) —
    deliberately not something this endpoint (or the container it runs in) can do to
    itself: it has no access to the host's git checkout or Docker socket, and
    shouldn't be given one just for this.
    """
    sha = _current_sha()
    if sha is None:
        return {
            "checked": False,
            "reason": "this build has no version baked in (a manual/local build, or a non-git install) — can't check for updates",
        }
    return await _compare_to_main(sha)
