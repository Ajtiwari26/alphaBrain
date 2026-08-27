import re

with open("alpha_worker/daemon.py", "r") as f:
    content = f.read()

# Fix execute_task_cycle
old_dispatch = """            # 4. Dispatch to adapter
            adapter = self.select_adapter(envelope.preferred_agent)
            result = await adapter.execute(
                task=envelope,
                worktree_path=worktree_path,
                base_commit=envelope.base_commit,
            )"""

new_dispatch = """            # 4. Dispatch to adapter
            adapter = self.select_adapter(envelope.preferred_agent)
            
            # ActionBroker integration
            from alpha_protocol.broker import ActionBroker
            broker = ActionBroker()
            broker_decision = broker.evaluate(envelope)
            
            # Dispatch to actual live adapter
            outcome = await adapter.dispatch(
                task=envelope,
                worktree_path=worktree_path,
                base_commit=envelope.base_commit,
            )
            
            result = evaluate_daemon_task_lifecycle(
                task=envelope,
                broker_decision=broker_decision,
                outcome=outcome,
            )"""

content = content.replace(old_dispatch, new_dispatch)

# Fix execute_remote_cycle
old_remote_dispatch = """            adapter = self.select_adapter(envelope.preferred_agent)
            result = await adapter.execute(envelope, worktree_path, envelope.base_commit)"""

new_remote_dispatch = """            adapter = self.select_adapter(envelope.preferred_agent)
            from alpha_protocol.broker import ActionBroker
            broker = ActionBroker()
            broker_decision = broker.evaluate(envelope)
            outcome = await adapter.dispatch(
                task=envelope,
                worktree_path=worktree_path,
                base_commit=envelope.base_commit,
            )
            result = evaluate_daemon_task_lifecycle(
                task=envelope,
                broker_decision=broker_decision,
                outcome=outcome,
            )"""

content = content.replace(old_remote_dispatch, new_remote_dispatch)

with open("alpha_worker/daemon.py", "w") as f:
    f.write(content)
