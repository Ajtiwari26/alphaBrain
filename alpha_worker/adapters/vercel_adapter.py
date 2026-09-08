import asyncio
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DeploymentResult:
    url: str
    status: str
    health_ok: bool


class VercelAdapter:
    def __init__(self, token: str, project_id: str | None = None):
        self.token = token
        self.project_id = project_id

    def _mask_secrets(self, text: str) -> str:
        if not self.token:
            return text
        return text.replace(self.token, "***")

    async def deploy_preview(self, worktree_path: Path) -> DeploymentResult:
        """Triggers a preview deployment using Vercel CLI."""
        cmd = ["vercel", "--token", self.token, "--yes", "--cwd", str(worktree_path)]
        if self.project_id:
            cmd.extend(["--project", self.project_id])

        # Execute deployment command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = self._mask_secrets(stderr.decode())
            raise RuntimeError(f"Vercel deployment failed: {error_msg}")

        output = stdout.decode()

        # Deployment URL extraction
        url_match = re.search(r'(https://[a-zA-Z0-9-]+\.vercel\.app)', output)
        if not url_match:
            err_output = stderr.decode()
            url_match = re.search(r'(https://[a-zA-Z0-9-]+\.vercel\.app)', err_output)

        if not url_match:
            lines = [line.strip() for line in output.split("\n") if line.strip()]
            if lines:
                url = lines[-1]
            else:
                raise RuntimeError("Failed to extract deployment URL from Vercel output.")
        else:
            url = url_match.group(1)

        # Status polling
        status = await self.poll_status(url)

        # Health check validation
        health_ok = False
        if status == "READY":
            health_ok = await self.check_health(url)

        return DeploymentResult(url=url, status=status, health_ok=health_ok)

    async def poll_status(self, url: str, timeout_seconds: int = 300) -> str:
        """Polls the deployment status using Vercel CLI."""
        cmd = ["vercel", "inspect", url, "--token", self.token]

        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout_seconds:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = self._mask_secrets(stderr.decode())
                raise RuntimeError(f"Vercel inspect failed: {error_msg}")

            output = stdout.decode()
            if "READY" in output:
                return "READY"
            if "ERROR" in output:
                return "ERROR"
            if "CANCELED" in output:
                return "CANCELED"

            await asyncio.sleep(5)

        return "TIMEOUT"

    async def check_health(self, url: str) -> bool:
        """Validates that the deployed URL is reachable and returns HTTP 200."""
        try:
            def fetch() -> bool:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as response:
                    return response.getcode() == 200

            return await asyncio.to_thread(fetch)
        except Exception:
            return False
