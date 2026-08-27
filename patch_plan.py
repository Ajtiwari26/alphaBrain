with open("testscript/run_live_kernel_proof.py", "r") as f:
    text = f.read()

text = text.replace(
    'from alpha_protocol import AcceptancePlan, AgentType, RiskClass, TaskEnvelope',
    'from alpha_protocol import AcceptancePlan, AgentType, GateCommand, GateType, RiskClass, TaskEnvelope'
)

old_env = """            envelope = TaskEnvelope(
                task_id=task_id,
                project_id=proj.id,
                repo=str(project_path),
                objective="Build responsive status page with health cards (HTML/CSS/JS) and add self-hosted browser QA under testscript/. Then exit.",
                allowed_paths=["."],
                risk_class=RiskClass.LOW,
                preferred_agent=AgentType.ANTIGRAVITY,
                requires_approval=True,
                retain_worktree_for_preview=True,
                acceptance_plan=AcceptancePlan(require_independent_review=False),
            )"""

new_env = """            envelope = TaskEnvelope(
                task_id=task_id,
                project_id=proj.id,
                repo=str(project_path),
                objective="Build responsive status page with health cards (HTML/CSS/JS) and add self-hosted browser QA under testscript/. Ensure you supply compatible package.json scripts for 'lint' and 'test' in the testscript directory. Then exit.",
                allowed_paths=["."],
                risk_class=RiskClass.LOW,
                preferred_agent=AgentType.ANTIGRAVITY,
                requires_approval=True,
                retain_worktree_for_preview=True,
                acceptance_plan=AcceptancePlan(
                    require_independent_review=False,
                    commands=[
                        GateCommand(
                            gate_type=GateType.LINT,
                            executable="npm",
                            args=["--prefix", "testscript", "run", "lint"]
                        ),
                        GateCommand(
                            gate_type=GateType.UNIT_TEST,
                            executable="npm",
                            args=["--prefix", "testscript", "test"]
                        )
                    ]
                ),
            )"""

text = text.replace(old_env, new_env)

with open("testscript/run_live_kernel_proof.py", "w") as f:
    f.write(text)
