"""browser-use自动化工具，支持会话管理的start和check action。"""

from typing import TYPE_CHECKING, Any, Literal, NoReturn

from strix.tools.registry import register_tool


if TYPE_CHECKING:
    from .browser_use_manager import BrowserUseManager


BrowserUseAction = Literal["start", "check", "status", "list"]


def _validate_task(action_name: str, task: str | None) -> None:
    if not task:
        raise ValueError(f"task参数对于 {action_name} action是必需的")


def _validate_session_id(action_name: str, session_id: str | None) -> None:
    if not session_id:
        raise ValueError(f"session_id参数对于 {action_name} action是必需的")


def _handle_start_action(
    manager: "BrowserUseManager",
    task: str | None = None,
    max_steps: int = 50,
) -> dict[str, Any]:
    """处理start action。"""
    _validate_task("start", task)
    assert task is not None
    
    return manager.start_session(task, max_steps)


def _handle_check_action(
    manager: "BrowserUseManager",
    session_id: str | None = None,
) -> dict[str, Any]:
    """处理check action。"""
    return manager.check_session(session_id)


def _handle_status_action(
    manager: "BrowserUseManager",
    session_id: str | None = None,
) -> dict[str, Any]:
    """处理status action。"""
    return manager.get_session_status(session_id)


def _handle_list_action(
    manager: "BrowserUseManager",
) -> dict[str, Any]:
    """处理list action。"""
    return manager.list_sessions()


def _raise_unknown_action(action: str) -> NoReturn:
    raise ValueError(f"未知action: {action}")


@register_tool(sandbox_execution=True)
def browser_use(
    action: BrowserUseAction,
    task: str | None = None,
    max_steps: int = 50,
    session_id: str | None = None,
) -> dict[str, Any]:
    """browser-use自动化工具，支持会话管理的start和check action。
    
    重要逻辑：
    1. start action: 创建新会话，browser-use独立持久化运行
    2. check action: 检查活动会话的URL变化
    3. status action: 获取会话状态
    4. list action: 列出所有会话
    
    Args:
        action: 操作类型，"start"、"check"、"status" 或 "list"
        task: 任务描述（仅start action需要）
        max_steps: 最大步数（仅start action需要，默认50）
        session_id: 会话ID（check/status action可选，默认使用活动会话）
        
    Returns:
        操作结果，包含会话信息和URL变化
    """
    from .browser_use_manager import get_browser_use_manager
    
    manager = get_browser_use_manager()
    
    try:
        start_actions = {"start"}
        check_actions = {"check"}
        status_actions = {"status"}
        list_actions = {"list"}
        
        if action in start_actions:
            return _handle_start_action(manager, task, max_steps)
        if action in check_actions:
            return _handle_check_action(manager, session_id)
        if action in status_actions:
            return _handle_status_action(manager, session_id)
        if action in list_actions:
            return _handle_list_action(manager)
        
        _raise_unknown_action(action)
        
    except (ValueError, RuntimeError) as e:
        return {
            "error": str(e),
            "action": action,
            "task": task,
            "session_id": session_id,
        }
