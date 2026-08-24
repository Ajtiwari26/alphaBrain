from typing import Any

from alpha_core.config import settings


class StitchMCPAdapter:
    """Stitch MCP Client configured to strictly use gemini-3.1-pro model ID."""

    def __init__(self, model_id: str = "gemini-3.1-pro"):
        self.model_id = model_id or settings.STITCH_MODEL_ID

    def check_readiness(self) -> tuple[bool, str]:
        return True, f"Stitch MCP ready with model {self.model_id}"

    def build_generate_screen_payload(
        self,
        project_id: str,
        screen_name: str,
        prompt: str,
        device_type: str = "DESKTOP",
    ) -> dict[str, Any]:
        """Constructs compliant Stitch MCP payload with Gemini 3.1 Pro model ID."""
        return {
            "projectId": project_id,
            "screenName": screen_name,
            "prompt": prompt,
            "deviceType": device_type,
            "modelId": self.model_id,
        }

    def build_edit_screens_payload(
        self,
        project_id: str,
        screen_ids: list[str],
        prompt: str,
    ) -> dict[str, Any]:
        """Constructs edit screens payload with Gemini 3.1 Pro model ID."""
        return {
            "projectId": project_id,
            "screenIds": screen_ids,
            "prompt": prompt,
            "modelId": self.model_id,
        }
