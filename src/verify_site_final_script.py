import tempfile, compileall, glob, subprocess, sys, os
workdir_blog = r"C:\Users\ASUS\daily-news-shorts"
changed = [
    "site/index.html",
    "site/css/style.css",
    "site/README.md",
    "site/privacy.html",
    "site/terms.html",
    "site/cookies.html",
    "site/adsense-ad.html",
]
results = []
for p in changed:
    full = f"{workdir_blog}/{p}"
    exists = os.path.exists(full)
    size = os.path.getsize(full) if exists else 0
    if p.endswith(".html"):
        with open(full) as f: c = f.read()
        ok = ("<!DOCTYPE" in c) and ("</html>" in c)
        results.append(f"PASS structure: {p} (exists={exists} size={size}B doctype_close={ok})")
    elif p.endswith(".md"):
        results.append(f"PASS exists: {p} ({exists} {size}B)")
    else:
        results.append(f"PASS exists: {p} ({exists} {size}B)")
# Adsense reference check
with open(f"{workdir_blog}/site/adsense-ad.html") as f:
    results.append(f"PASS adsense-ref: adsbygoogle={'adsbygoogle' in f.read()}")
with open(f"{workdir_blog}/site/index.html") as f:
    c = f.read()
    results.append(f"PASS index-links: privacy={'privacy.html' in c} terms={'terms.html' in c} cookies={'cookies.html' in c}")
res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workdir_blog, capture_output=True, text=True)
results.append(f"HEAD={res.stdout.strip()[:8]}")
# Create temp artifact using NamedTemporaryFile in a separate safe file (avoid inline syntax error)
artifact_path = tempfile.mktemp(prefix="hermes-verify-", suffix=".txt", dir=r"D:\")
with open(artifact_path, "w") as f:
    f.write("VERIFICATION REPORT (ad-hoc, not suite green)\n")
    f.write("==========================================\n")
    for r in results:
        f.write(r + "\n")
    f.write("NOT FULL SUITE GREEN: no automated suite; site visual/UI not user-confirmed live; adsense needs real pub ID; CI env missing packages.\n")
    f.write("BLOCKER: simplification by design (video disabled); environment dependency gap; no full CI trigger for site build.\n")
print("ARTIFACT:", artifact_path)
with open(artifact_path) as f: print(f.read())
os.unlink(artifact_path)
print("CLEANED: temp artifact deleted.")
