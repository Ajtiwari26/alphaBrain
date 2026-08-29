import asyncio
import os
from google.genai import types
from livekit import rtc
from livekit.agents import Agent, AgentSession, room_io
from livekit.plugins import google
import livekit.plugins.google.realtime.realtime_api as realtime_api

original_build = realtime_api.RealtimeSession._build_connect_config

def patched_build(self):
    conf = original_build(self)
    # Clear out unsupported fields for Live Translate
    conf.system_instruction = None
    conf.tools = None
    conf.history_config = None
    
    if hasattr(self._realtime_model, "translation_config") and self._realtime_model.translation_config:
        conf.translation_config = self._realtime_model.translation_config
    return conf

realtime_api.RealtimeSession._build_connect_config = patched_build

async def run_agent():
    print("Monkey-patched successfully!")
    model = google.realtime.RealtimeModel(
        model="gemini-3.5-live-translate-preview",
        api_key=os.environ.get("GOOGLE_API_KEY"),
        instructions=""
    )
    model.translation_config = types.TranslationConfig(
        target_language_code="es",
        echo_target_language=False,
    )
    
    print("Model initialized. Patch is ready!")
    
if __name__ == "__main__":
    asyncio.run(run_agent())
