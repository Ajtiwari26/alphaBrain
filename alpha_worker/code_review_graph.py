import ast
import subprocess
from pathlib import Path

def extract_code_review_graph(worktree_path: str, diff_content: str) -> str:
    """
    Parses a unified diff and performs localized static analysis to build 
    a Code Review Graph artifact (changed files, methods, impacts).
    """
    changed_files = []
    for line in diff_content.splitlines():
        if line.startswith("+++ b/"):
            changed_files.append(line[6:].strip())

    graph_md = ["# Code Review Graph Artifact\n"]
    if not changed_files:
        graph_md.append("No files changed.")
        return "\n".join(graph_md)

    graph_md.append("## Changed Files & Dependency Impacts\n")
    
    for fpath in changed_files:
        graph_md.append(f"### `{fpath}`")
        full_path = Path(worktree_path) / fpath
        
        if full_path.exists() and fpath.endswith(".py"):
            try:
                tree = ast.parse(full_path.read_text(errors="ignore"))
                classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                
                if classes or funcs:
                    graph_md.append("**Symbols Modified/Added:**")
                    for c in classes:
                        graph_md.append(f"- Class: `{c}`")
                    for f in funcs:
                        graph_md.append(f"- Function: `{f}`")
                
                module_name = fpath.replace("/", ".").replace(".py", "")
                if module_name.endswith(".__init__"):
                    module_name = module_name[:-9]
                
                try:
                    # Basic grep to find dependencies (who imports this module)
                    grep_cmd = ["git", "grep", "-l", module_name]
                    impacts = subprocess.check_output(grep_cmd, cwd=worktree_path, text=True, stderr=subprocess.DEVNULL).splitlines()
                    impacts = [imp for imp in impacts if imp != fpath and imp.endswith(".py")]
                    if impacts:
                        graph_md.append("\n**Dependency Impacts (Files that may be affected):**")
                        for imp in impacts[:5]:
                            graph_md.append(f"- `{imp}`")
                        if len(impacts) > 5:
                            graph_md.append(f"- ... and {len(impacts) - 5} more.")
                except subprocess.CalledProcessError:
                    pass
            except SyntaxError:
                graph_md.append("*(Syntax Error parsing file)*")
        elif full_path.exists():
            graph_md.append("*(Non-Python file)*")
        else:
            graph_md.append("*(File deleted)*")
        graph_md.append("")
    
    return "\n".join(graph_md)
