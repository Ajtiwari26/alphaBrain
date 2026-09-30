import json
import logging
import os
import time
import uuid
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class CallDispatchResult:
    call_id: str
    status: str
    provider: str
    error: str | None = None


@dataclass
class InAppCallState:
    call_id: str
    caller_name: str
    caller_role: str
    title: str
    prompt_summary: str
    status: str
    created_at: float
    task_id: str | None = None
    answered_at: float | None = None
    ended_at: float | None = None


class AgentLineVoiceBridge:
    _active_inapp_call: InAppCallState | None = None

    def dispatch_inapp_call(self, caller_name: str, caller_role: str, title: str, prompt_summary: str, task_id: str | None = None) -> dict:
        call_id = str(uuid.uuid4())
        self.__class__._active_inapp_call = InAppCallState(
            call_id=call_id,
            caller_name=caller_name,
            caller_role=caller_role,
            title=title,
            prompt_summary=prompt_summary,
            status='ringing',
            created_at=time.time(),
            task_id=task_id
        )
        return self.__class__._active_inapp_call.__dict__

    def get_active_call(self) -> dict | None:
        call = self.__class__._active_inapp_call
        if call and call.status == 'ringing' and time.time() - call.created_at <= 60:
            return call.__dict__
        return None

    def respond_to_call(self, call_id: str, action: str) -> dict:
        call = self.__class__._active_inapp_call
        if call and call.call_id == call_id and call.status == 'ringing':
            call.status = 'accepted' if action == 'accept' else 'declined'
            if action == 'accept':
                call.answered_at = time.time()
            else:
                call.ended_at = time.time()
            return call.__dict__
        return {"error": "Call not found or not ringing"}

    def __init__(
        self,
        plivo_auth_id: str | None = None,
        plivo_auth_token: str | None = None,
        storage_path: str = "voice_briefings.json"
    ):
        self.plivo_auth_id = plivo_auth_id or os.environ.get("PLIVO_AUTH_ID")
        self.plivo_auth_token = plivo_auth_token or os.environ.get("PLIVO_AUTH_TOKEN")
        self.storage_path = storage_path
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w") as f:
                json.dump([], f)

    def _save_briefing(self, briefing: dict):
        briefings = self.get_recent_briefings()
        briefings.append(briefing)
        with open(self.storage_path, "w") as f:
            json.dump(briefings, f)

    def get_recent_briefings(self) -> list[dict]:
        if not os.path.exists(self.storage_path):
            return []
        try:
            with open(self.storage_path) as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def dispatch_approval_call(
        self, to_number: str, task_id: str, title: str, preview_url: str
    ) -> CallDispatchResult:
        script = (
            f"AlphaBrain Urgent Approval: Task {task_id} requires founder sign-off. "
            f"{title}. Review at {preview_url}."
        )

        if self.plivo_auth_id and self.plivo_auth_token:
            try:
                # Attempt Plivo API call
                url = f"https://api.plivo.com/v1/Account/{self.plivo_auth_id}/Call/"
                auth = (self.plivo_auth_id, self.plivo_auth_token)

                payload = {
                    "to": to_number,
                    "from": "1800ALPHABRAIN",
                    "answer_url": "http://example.com/answer/",  # Placeholder
                    "answer_method": "GET"
                }

                response = requests.post(url, auth=auth, json=payload, timeout=5)

                if response.status_code == 201:
                    data = response.json()
                    call_id = data.get("request_uuid", str(uuid.uuid4()))
                    return CallDispatchResult(
                        call_id=call_id, status="success", provider="plivo"
                    )

                logger.warning(
                    f"Plivo API failed with status {response.status_code}. "
                    "Falling back to simulated mode."
                )

            except requests.RequestException as e:
                logger.warning(f"Plivo API connection error: {e}. Falling back to simulated mode.")

        # Fallback to simulated local voice mode
        call_id = str(uuid.uuid4())

        briefing = {
            "call_id": call_id,
            "timestamp": time.time(),
            "to_number": to_number,
            "task_id": task_id,
            "script": script,
            "status": "simulated_success"
        }

        self._save_briefing(briefing)

        print(f"[SIMULATED TELEPHONY DISPATCH] Call to {to_number}: {script}")

        return CallDispatchResult(
            call_id=call_id,
            status="simulated_success",
            provider="simulated_local"
        )
