import asyncio
from pathlib import Path
from alpha_core.db.connection import get_session_factory
from alpha_protocol.gates import AcceptancePlan, GateCommand, GateType
from alpha_protocol.enums import RiskClass

from alpha_core.self_development import create_self_improvement_task, SelfImprovementRequest
from alpha_core.config import settings

async def main():
    repo_path = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain")
    
    # Needs to match the S1 requirements
    request = SelfImprovementRequest(
        source_repo=repo_path,
        allowed_paths=(
            "alpha_meet/frontend/index.html",
            "alpha_meet/frontend/css/meet.css",
            "alpha_meet/frontend/js/meet.js"
        ),
        founder_identity="ajtiwari",
        requires_approval=True,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    
    plan = AcceptancePlan(
        commands=[
            GateCommand(gate_type=GateType.LINT, executable="ruff", args=["check", "alpha_meet/"]),
        ],
        required_gates=[GateType.INDEPENDENT_REVIEW, GateType.CODE_REVIEW_GRAPH, GateType.LINT],
        require_independent_review=True,
    )
    
    factory = get_session_factory()
    async with factory() as session:
        try:
            task = await create_self_improvement_task(
                session,
                request,
                project_id="prj_alphabrain_self",
                task_id="tsk_self_meet_darkmode",
                objective="Implement a Dark Mode toggle in the Eva Meet UI.",
                detailed_instructions="Add a toggle button in the bottom control strip of index.html. Update meet.js to handle the toggle state. Update meet.css to invert --color-paper to dark (#111) and --color-ink to light (#fff) when the dark mode class is active, preserving the Deploymate aesthetic.",
                acceptance_plan=plan,
            )
            await session.commit()
            print(f"Task created successfully: {task.id}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
