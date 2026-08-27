with open("docs/architecture/agy-junior-execution-contract.md", "r") as f:
    text = f.read()

text = text.replace(
    "- NO production side effects or database mutation outside local sqlite/test bounds.",
    "- NO production side effects or database mutation outside local sqlite/test bounds.\n- NO execution of unauthorized external network fetches or dependency installation commands (`npm install`, `npm ci`, `npx playwright install`, `curl`, `wget`) unless explicitly granted by a future policy exception."
)

with open("docs/architecture/agy-junior-execution-contract.md", "w") as f:
    f.write(text)
