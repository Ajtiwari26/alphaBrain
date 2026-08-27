with open("testscript/run_live_kernel_proof.py", "r") as f:
    text = f.read()

setup_git = """
def setup_git_repository(project_path: Path) -> None:
    gitignore_path = project_path / ".gitignore"
    with gitignore_path.open("w") as f:
        f.write(".alpha_live_run\\nlive_kernel.db\\n")

    try:
        subprocess.run(["git", "init"], cwd=project_path, check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", ".gitignore"], cwd=project_path, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit from live proof harness"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True
        )

        status_result = subprocess.run(["git", "status", "--porcelain"], cwd=project_path, check=True, capture_output=True, text=True)
        if status_result.stdout.strip():
            raise RuntimeError(f"Git status is not clean after init: {status_result.stdout.strip()}")
            
        subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_path, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git setup failed: command '{' '.join(e.cmd)}' returned {e.returncode}. stderr: {e.stderr}")

"""

text = text.replace("def create_safe_project_dir", setup_git + "def create_safe_project_dir")

text = text.replace(
    'subprocess.run(["git", "init"], cwd=project_path, check=True, capture_output=True)',
    """try:
        setup_git_repository(project_path)
    except Exception as e:
        print(f"Failed to setup git repository: {e}")
        sys.exit(1)"""
)

with open("testscript/run_live_kernel_proof.py", "w") as f:
    f.write(text)
