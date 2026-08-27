with open("testscript/test_live_kernel_safety.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if '(project_path / "live_kernel.db").write_text("sqlite")' in line:
        new_lines.append('    (project_path / "live_kernel.db-journal").write_text("j")\n')
        new_lines.append('    (project_path / "live_kernel.db-wal").write_text("w")\n')
        new_lines.append('    (project_path / "live_kernel.db-shm").write_text("s")\n')

with open("testscript/test_live_kernel_safety.py", "w") as f:
    f.writelines(new_lines)
