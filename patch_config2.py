with open("alpha_core/config.py", "r") as f:
    text = f.read()

import re
text = re.sub(
    r'    def validate_worker_lease_duration\(cls, v: int\) -> int:\n        if v < 300 or v > 7200:\n            raise ValueError\("WORKER_LEASE_DURATION_SECONDS must be between 300 and 7200"\)\n        return v\n\n\n    @field_validator\("WORKER_LEASE_DURATION_SECONDS"\)',
    '    @field_validator("WORKER_LEASE_DURATION_SECONDS")',
    text
)

text = re.sub(
    r'    @field_validator\("WORKER_LEASE_DURATION_SECONDS"\)\n    @field_validator\("WORKER_LEASE_DURATION_SECONDS"\)',
    '    @field_validator("WORKER_LEASE_DURATION_SECONDS")',
    text
)

with open("alpha_core/config.py", "w") as f:
    f.write(text)
