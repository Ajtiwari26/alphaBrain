with open("alpha_worker/daemon.py", "r") as f:
    content = f.read()

content = content.replace("            if (\n                result\n                and result.status == TaskStatus.VERIFIED", "            print(f'Condition check: {result.status=} {envelope.retain_worktree_for_preview=} {worktree_path=}')\n            if (\n                result\n                and result.status == TaskStatus.VERIFIED")

with open("alpha_worker/daemon.py", "w") as f:
    f.write(content)
