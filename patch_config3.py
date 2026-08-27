with open("alpha_core/config.py", "r") as f:
    text = f.read()

text = text.replace(
    '    @field_validator("WORKER_LEASE_DURATION_SECONDS")\n    def validate_worker_lease_duration(cls, v: int) -> int:',
    '    @field_validator("WORKER_LEASE_DURATION_SECONDS")\n    @classmethod\n    def validate_worker_lease_duration(cls, v: int) -> int:'
)

with open("alpha_core/config.py", "w") as f:
    f.write(text)
