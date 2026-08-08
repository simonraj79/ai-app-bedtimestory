"""Deploy frontend/ to Vercel by direct file upload.

Needed because Vercel's GitHub App cannot see this private repo, so `git push`
redeploys the Render backend but not the frontend. Delete this script once the
Vercel project is linked to GitHub and auto-deploy works.

Run from the project root:  python scripts/deploy_frontend.py
Requires VERCEL_TOKEN in .vercel.env (gitignored).
"""
import base64
import pathlib
import re
import sys
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEAM = "team_6Mc9jwQee8nmnfyfV8IJPAlx"
PROJECT = "prj_IRlDJCZYjQNittWSAbm8cKJWle2O"

match = re.search(r"^VERCEL_TOKEN=(.+)$", (ROOT / ".vercel.env").read_text(), re.M)
if not match or "PASTE" in match.group(1):
    sys.exit("No VERCEL_TOKEN in .vercel.env - create one at "
             "https://vercel.com/account/settings/tokens")
token = match.group(1).strip()

files = []
for path in sorted((ROOT / "frontend").iterdir()):
    if path.is_file():
        files.append({
            "file": path.name,
            "data": base64.b64encode(path.read_bytes()).decode(),
            "encoding": "base64",
        })
        print(f"  + {path.name} ({path.stat().st_size} bytes)")

with httpx.Client(timeout=120.0) as client:
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        f"https://api.vercel.com/v13/deployments?teamId={TEAM}&forceNew=1",
        headers=headers,
        json={
            "name": "ai-app-bedtimestory",
            "project": PROJECT,
            "target": "production",
            "files": files,
            # outputDirectory must be null: the files above are already at the
            # deployment root. The project's "frontend" setting applies to Git
            # builds, where the repo root is the deployment root.
            "projectSettings": {
                "framework": None,
                "buildCommand": None,
                "installCommand": None,
                "outputDirectory": None,
            },
        },
    )
    if r.status_code >= 400:
        sys.exit(f"  deploy failed: {r.status_code} {r.text[:400]}")

    deployment_id = r.json()["id"]
    print(f"  deployment {deployment_id}")

    for _ in range(60):
        state = client.get(
            f"https://api.vercel.com/v13/deployments/{deployment_id}?teamId={TEAM}",
            headers=headers,
        ).json()
        ready = state.get("readyState")
        if ready in ("READY", "ERROR", "CANCELED"):
            print(f"  {ready}")
            for alias in state.get("alias") or []:
                print(f"  https://{alias}")
            sys.exit(0 if ready == "READY" else 1)
        time.sleep(5)
    sys.exit("  timed out waiting for the deployment to become ready")
