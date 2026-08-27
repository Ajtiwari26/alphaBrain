import re

with open("alpha_worker/adapters/antigravity_live.py") as f:
    text = f.read()

# I will replace the body of dispatch with a new one.
start_idx = text.find("    async def dispatch(")
end_idx = text.find("    def _needs_compliance_repair(dispatch: AntigravityDispatch) -> bool:")

old_dispatch = text[start_idx:end_idx]

new_dispatch = """    async def dispatch(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        attempt_id: str,
        session_dir: Path | None = None,
    ) -> AntigravityDispatch:
        \"\"\"Create/resume only task project conversation, then parse AGY event evidence.\"\"\"

        ready, reason = self.check_readiness()
        if not ready:
            raise RuntimeError(reason)

        forbid_deps = (
            "dependency-free" in (task.objective or "").lower()
            or "no external dependency acquisition" in (task.objective or "").lower()
            or "dependency-free" in (task.detailed_instructions or "").lower()
            or "no external dependency acquisition" in (task.detailed_instructions or "").lower()
        )

        max_attempts = settings.MAX_ELIGIBLE_ATTEMPTS if settings.MODEL_ROUTING_ENABLED else 1
        attempts_made = 0

        while attempts_made < max_attempts:
            attempts_made += 1

            req = RoutingRequest(
                project_id=task.project_id,
                task_id=task.task_id,
                attempt_id=attempt_id,
                stage=ExecutionStage.IMPLEMENT,
                risk_class=task.risk_class.value,
                complexity_class="medium"
            )
            decision = call_model_router(req)
            
            if decision.status == RoutingDecisionStatus.BLOCKED:
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="Router blocked execution: " + ", ".join(decision.rationale_codes),
                    tool_names=(), final_message="", transcript_path=None
                )
            if decision.status == RoutingDecisionStatus.RATE_LIMITED:
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="Router rate limited globally",
                    tool_names=(), final_message="", transcript_path=None
                )

            account_id = decision.account_id or "legacy_default"
            model = decision.model or settings.ANTIGRAVITY_MODEL
            effort = decision.effort or settings.ANTIGRAVITY_EFFORT

            try:
                async with acquire_credential_lease(account_id) as lease:
                    conversation_id, is_new_project = self._get_project_conversation(task)
                    raw = await self._run_agy(
                        prompt=self._build_task_prompt(task, worktree_path, is_new_project),
                        worktree_path=worktree_path,
                        conversation_id=conversation_id,
                        is_new_project=is_new_project,
                        timeout_seconds=min(
                            task.lease_timeout_seconds, settings.ANTIGRAVITY_TASK_TIMEOUT_SECONDS
                        ),
                        log_path=self._turn_log_path(session_dir, "implementation"),
                        model=model,
                        effort=effort,
                    )
                    
                    if raw["returncode"] == 429:
                        report_model_outcome(account_id, model, "rate_limit")
                        if attempts_made >= max_attempts:
                            return AntigravityDispatch(
                                conversation_id=conversation_id or "",
                                completed=False,
                                blocked_reason="exhausted eligible accounts via 429",
                                tool_names=(), final_message="", transcript_path=None
                            )
                        continue
                        
                    report_model_outcome(account_id, model, "success")

                    dispatch_res = self._parse_agy_result(
                        raw,
                        expected_qa_gates=tuple(gate.value for gate in task.acceptance_plan.required_gates),
                        expected_project_id=task.project_id,
                        forbid_external_dependencies=forbid_deps,
                    )
                    if not dispatch_res.conversation_id:
                        raise RuntimeError("AGY result did not include a conversation ID")
                    dispatch_res = replace(
                        dispatch_res,
                        transcript_path=self._turn_log_path(session_dir, "implementation"),
                    )
                    if is_new_project:
                        self._write_record(
                            self._project_store_path(task.project_id),
                            {
                                "project_id": task.project_id,
                                "repo_path": str(Path(task.repo).expanduser().resolve()),
                                "conversation_id": dispatch_res.conversation_id,
                                "created_at": datetime.now(UTC).isoformat(),
                                "updated_at": datetime.now(UTC).isoformat(),
                                "source": "official_agy_cli_new_project",
                            },
                        )
                    if self._needs_compliance_repair(dispatch_res):
                        repair_raw = await self._run_agy(
                            prompt=self._build_compliance_repair_prompt(task, worktree_path, dispatch_res),
                            worktree_path=worktree_path,
                            conversation_id=dispatch_res.conversation_id,
                            is_new_project=False,
                            timeout_seconds=min(
                                task.lease_timeout_seconds, settings.ANTIGRAVITY_TASK_TIMEOUT_SECONDS
                            ),
                            log_path=self._turn_log_path(session_dir, "compliance-repair"),
                            model=model,
                            effort=effort,
                        )
                        if repair_raw["returncode"] == 429:
                            report_model_outcome(account_id, model, "rate_limit")
                            if attempts_made >= max_attempts:
                                return AntigravityDispatch(
                                    conversation_id=dispatch_res.conversation_id,
                                    completed=False,
                                    blocked_reason="exhausted eligible accounts via 429",
                                    tool_names=(), final_message="", transcript_path=None
                                )
                            continue
                        
                        dispatch_res = self._parse_agy_result(
                            self._combine_turn_evidence(raw, repair_raw),
                            expected_qa_gates=tuple(gate.value for gate in task.acceptance_plan.required_gates),
                            expected_project_id=task.project_id,
                            forbid_external_dependencies=forbid_deps,
                        )
                        dispatch_res = replace(
                            dispatch_res,
                            transcript_path=self._turn_log_path(session_dir, "compliance-repair"),
                        )
                    if dispatch_res.completed:
                        audit_raw = await self._run_agy(
                            prompt=self._build_qa_audit_prompt(task, worktree_path),
                            worktree_path=worktree_path,
                            conversation_id=dispatch_res.conversation_id,
                            is_new_project=False,
                            timeout_seconds=min(
                                task.lease_timeout_seconds, settings.ANTIGRAVITY_TASK_TIMEOUT_SECONDS
                            ),
                            log_path=self._turn_log_path(session_dir, "qa-audit"),
                            model=model,
                            effort=effort,
                        )
                        if audit_raw["returncode"] == 429:
                            report_model_outcome(account_id, model, "rate_limit")
                            if attempts_made >= max_attempts:
                                return AntigravityDispatch(
                                    conversation_id=dispatch_res.conversation_id,
                                    completed=False,
                                    blocked_reason="exhausted eligible accounts via 429",
                                    tool_names=(), final_message="", transcript_path=None
                                )
                            continue
                            
                        dispatch_res = self._parse_agy_result(
                            audit_raw,
                            expected_qa_gates=tuple(gate.value for gate in task.acceptance_plan.required_gates),
                            expected_project_id=task.project_id,
                            require_qa_audit=True,
                            forbid_external_dependencies=forbid_deps,
                        )
                        dispatch_res = replace(
                            dispatch_res,
                            transcript_path=self._turn_log_path(session_dir, "qa-audit"),
                        )

                    return dispatch_res

            except CredentialLockTimeoutError:
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="credential_lock_timeout",
                    tool_names=(), final_message="", transcript_path=None
                )
            except SwitchCommandError:
                report_model_outcome(account_id, model, "auth_failed")
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="auth_failed",
                    tool_names=(), final_message="", transcript_path=None
                )
            except IdentityMismatchError:
                report_model_outcome(account_id, model, "auth_failed")
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="auth_failed",
                    tool_names=(), final_message="", transcript_path=None
                )

        return AntigravityDispatch(
            conversation_id="",
            completed=False,
            blocked_reason="exhausted eligible accounts",
            tool_names=(), final_message="", transcript_path=None
        )

"""

new_text = text[:start_idx] + new_dispatch + text[end_idx:]
with open("alpha_worker/adapters/antigravity_live.py", "w") as f:
    f.write(new_text)

