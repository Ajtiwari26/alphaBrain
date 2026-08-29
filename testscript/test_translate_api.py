import asyncio
import os
from google import genai
from google.genai import types

async def test_translate():
    api_key = os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text="Hello")]),
        translation_config=types.TranslationConfig(
            target_language_code="es",
            echo_target_language=False,
        )
    )

    try:
        print("Connecting to gemini-3.5-live-translate-preview with system instruction...")
        async with client.aio.live.connect(
            model="gemini-3.5-live-translate-preview",
            config=config
        ) as session:
            print("Connected successfully!")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_translate())
