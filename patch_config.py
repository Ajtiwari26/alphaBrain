with open("alpha_core/config.py", "r") as f:
    text = f.read()

text = text.replace(
    '    ANTIGRAVITY_TASK_TIMEOUT_SECONDS: int = int(\n        os.getenv("ANTIGRAVITY_TASK_TIMEOUT_SECONDS", "1200")\n    )',
    '    ANTIGRAVITY_TASK_TIMEOUT_SECONDS: int = int(\n        os.getenv("ANTIGRAVITY_TASK_TIMEOUT_SECONDS", "1200")\n    )\n    WORKER_LEASE_DURATION_SECONDS: int = int(os.getenv("WORKER_LEASE_DURATION_SECONDS", "1800"))'
)

validator_code = """
    @field_validator("WORKER_LEASE_DURATION_SECONDS")
    def validate_worker_lease_duration(cls, v: int) -> int:
        if v < 300 or v > 7200:
            raise ValueError("WORKER_LEASE_DURATION_SECONDS must be between 300 and 7200")
        return v
"""
text = text.replace(
    '    @field_validator("ANTIGRAVITY_EFFORT")',
    validator_code + '\n    @field_validator("ANTIGRAVITY_EFFORT")'
)

with open("alpha_core/config.py", "w") as f:
    f.write(text)

with open(".env.example", "r") as f:
    env_text = f.read()

env_text = env_text.replace(
    'ANTIGRAVITY_TASK_TIMEOUT_SECONDS=1200',
    'ANTIGRAVITY_TASK_TIMEOUT_SECONDS=1200\nWORKER_LEASE_DURATION_SECONDS=1800'
)

with open(".env.example", "w") as f:
    f.write(env_text)
