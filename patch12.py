with open("testscript/run_live_kernel_proof.py", "r") as f:
    text = f.read()

text = text.replace(
    'f.write(".alpha_live_run\\nlive_kernel.db\\n")',
    'f.write(".alpha_live_run\\nlive_kernel.db\\nlive_kernel.db-journal\\nlive_kernel.db-wal\\nlive_kernel.db-shm\\n")'
)

with open("testscript/run_live_kernel_proof.py", "w") as f:
    f.write(text)
