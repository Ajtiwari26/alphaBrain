with open("docs/architecture/agy-junior-execution-contract.md", "r") as f:
    text = f.read()

text = text.replace(
    "- NO execution of unauthorized external network fetches or dependency installation commands (`npm install`, `npm ci`, `npx playwright install`, `curl`, `wget`) unless explicitly granted by a future policy exception.",
    "- NO execution of unauthorized external network fetches or dependency installation commands (`npm install`, `npm ci`, `npx playwright install`, `curl`, `wget`) unless explicitly granted by a future policy exception (Deferred: future Dependency Acquisition Policy needs a founder-approved immutable package/lockfile/network contract; not implemented now)."
)

with open("docs/architecture/agy-junior-execution-contract.md", "w") as f:
    f.write(text)
