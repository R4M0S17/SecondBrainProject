from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from core.agents.state_store import AgentProfile
from core.tools.registry import ToolDefinition, ToolRegistry

LLM_BLOCKED_TOOLS: frozenset[str] = frozenset({
    "upload_file",
    "run_script",
})


def is_llm_allowed(tool_name: str) -> bool:
    return tool_name not in LLM_BLOCKED_TOOLS


@dataclass
class PolicyResult:
    approved: bool
    requires_user_confirmation: bool
    reason: str | None
    sanitized_args: dict


class PolicyEngine:
    """Validate tool calls against agent authorization + path scoping.

    Confirmation gating is owned by ``AgentRuntime._requires_confirmation``,
    which reads the *same* ``ToolDefinition.requires_confirmation`` flag that
    ``PolicyEngine.validate_call()`` surfaces in ``PolicyResult``. Tests in
    ``tests/test_tool_governance.py`` assert the flag at the registry layer;
    ``tests/test_tool_confirmation.py`` covers the runtime pause path.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        authorized_write_paths: list[str],
        watched_paths: list[str],
    ) -> None:
        self._registry = registry
        self._write_paths = [str(Path(p).resolve()) for p in authorized_write_paths]
        self._read_paths = [str(Path(p).resolve()) for p in watched_paths]

    def _is_under(self, path: str, authorized: list[str]) -> bool:
        resolved = Path(path).resolve()
        for auth in authorized:
            try:
                resolved.relative_to(Path(auth).resolve())
                return True
            except ValueError:
                continue
        return False

    async def validate_call(
        self,
        tool: ToolDefinition,
        args: dict,
        agent: AgentProfile,
    ) -> PolicyResult:
        if not self._registry.is_authorized(tool.name, agent):
            return PolicyResult(
                approved=False,
                requires_user_confirmation=False,
                reason=f"Agent '{agent.name}' is not authorized to use '{tool.name}'",
                sanitized_args={},
            )

        sanitized = dict(args)

        if tool.name == "read_file":
            path = args.get("path", "")
            if not self._is_under(path, self._read_paths):
                return PolicyResult(
                    approved=False,
                    requires_user_confirmation=False,
                    reason=f"read_file: path '{path}' is outside watched_paths",
                    sanitized_args=sanitized,
                )

        if tool.name == "write_file":
            path = args.get("path", "")
            if not self._is_under(path, self._write_paths):
                return PolicyResult(
                    approved=False,
                    requires_user_confirmation=False,
                    reason=f"write_file: path '{path}' is outside authorized_write_paths",
                    sanitized_args=sanitized,
                )
            sanitized.pop("content", None)

        if tool.name == "execute_python":
            code = args.get("code", "")
            sanitized["code"] = f"<{len(code)} chars>"

        if tool.name == "create_python_file":
            code = args.get("code", "")
            sanitized["code"] = f"<{len(code)} chars>"

        if tool.name in ("run_script",):
            path = args.get("filepath", "")
            if path and not self._is_under(path, self._write_paths):
                return PolicyResult(
                    approved=False,
                    requires_user_confirmation=False,
                    reason=f"run_script: path '{path}' is outside authorized_write_paths",
                    sanitized_args=sanitized,
                )

        if tool.name == "delete_file":
            path = args.get("path", "")
            if path and not self._is_under(path, self._write_paths):
                return PolicyResult(
                    approved=False,
                    requires_user_confirmation=False,
                    reason=f"delete_file: path '{path}' is outside authorized_write_paths",
                    sanitized_args=sanitized,
                )

        if tool.name == "create_directory":
            path = args.get("path", "")
            if path and not self._is_under(path, self._write_paths):
                return PolicyResult(
                    approved=False,
                    requires_user_confirmation=False,
                    reason=f"create_directory: path '{path}' is outside authorized_write_paths",
                    sanitized_args=sanitized,
                )

        if tool.name == "list_directory":
            path = args.get("path", "")
            if path and not self._is_under(path, self._read_paths):
                return PolicyResult(
                    approved=False,
                    requires_user_confirmation=False,
                    reason=f"list_directory: path '{path}' is outside watched_paths",
                    sanitized_args=sanitized,
                )

        if tool.name == "search_files":
            base_path = args.get("base_path", "")
            if base_path and not self._is_under(base_path, self._read_paths):
                return PolicyResult(
                    approved=False,
                    requires_user_confirmation=False,
                    reason=f"search_files: base_path '{base_path}' is outside watched_paths",
                    sanitized_args=sanitized,
                )

        logger.debug("PolicyEngine: approved tool={} agent={}", tool.name, agent.name)
        return PolicyResult(
            approved=True,
            requires_user_confirmation=tool.requires_confirmation,
            reason=None,
            sanitized_args=sanitized,
        )
