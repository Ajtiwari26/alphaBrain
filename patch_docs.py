with open("docs/architecture/agy-junior-execution-contract.md", "a") as f:
    f.write("\n### Gate Evidence Persistence\nAll gate evidence items submitted within the QA Manifest (whether the task is verified or retryable-failed) are durably recorded as individual `GateEvidenceRecord` rows mapped to the specific attempt, ensuring auditability of each individual check.\n")
