import re
with open("testscript/run_live_kernel_proof.py", "r") as f:
    text = f.read()

new_objective = '"Build a responsive health-status page built only with HTML/CSS/vanilla browser JavaScript. Create testscript/lint.mjs and testscript/test.mjs using Node built-ins only; no package.json, no node_modules, no dependencies, no external network access. Dependency-free proof. Browser smoke is not declared for this zero-dependency proof. (Future follow-up: fully browser-tested projects require an explicit local/preprovisioned browser smoke gate.) Then exit."'

text = re.sub(r'"Build a responsive health-status page.*?Then exit."', new_objective, text)

with open("testscript/run_live_kernel_proof.py", "w") as f:
    f.write(text)
