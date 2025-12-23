"""browser-use会话管理器（单例）。"""

import atexit
import hashlib
import signal
import sys
import threading
import time
from typing import Any, Dict, Optional

from .browser_use_instance import BrowserUseInstance


class BrowserUseManager:
    """browser-use会话管理器（单例），管理所有会话。"""
    
    _instance: Optional['BrowserUseManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'BrowserUseManager':
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance
    
    def _init_manager(self) -> None:
        self.sessions: Dict[str, BrowserUseInstance] = {}
        self.active_session_id: Optional[str] = None
        self._manager_lock = threading.Lock()
        
        self._register_cleanup_handlers()
    
    def _register_cleanup_handlers(self) -> None:
        """注册清理处理器（参考tab_manager.py）。"""
        atexit.register(self._cleanup_all_sessions)
        
        # 注册信号处理器
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._signal_handler)
            except (ValueError, OSError):
                pass
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """信号处理器。"""
        self._cleanup_all_sessions()
        sys.exit(0)
    
    def _cleanup_all_sessions(self) -> None:
        """清理所有会话。"""
        with self._manager_lock:
            for session_id, session in list(self.sessions.items()):
                try:
                    session.stop()
                except Exception:
                    pass
            self.sessions.clear()
            self.active_session_id = None
    
    @staticmethod
    def _generate_session_id(task: str, max_steps: int) -> str:
        """生成会话ID。"""
        content = f"{task}:{max_steps}:{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def start_session(self, task: str, max_steps: int = 50) -> Dict[str, Any]:
        """启动新会话。"""
        with self._manager_lock:
            # 检查是否已有活动会话
            if self.active_session_id and self.active_session_id in self.sessions:
                active_session = self.sessions[self.active_session_id]
                if active_session.is_running:
                    raise RuntimeError(
                        f"已有活动会话 {self.active_session_id} 在运行中，"
                        "请先停止或使用check检查"
                    )
            
            # 生成会话ID
            session_id = self._generate_session_id(task, max_steps)
            
            # 创建新会话
            try:
                session = BrowserUseInstance(session_id, task, max_steps)
                self.sessions[session_id] = session
                self.active_session_id = session_id
            except Exception as e:
                if session_id in self.sessions:
                    del self.sessions[session_id]
                if self.active_session_id == session_id:
                    self.active_session_id = None
                raise RuntimeError(f"启动browser-use会话失败: {e}") from e
            
            return {
                "session_id": session_id,
                "task": task,
                "max_steps": max_steps,
                "start_time": session.start_time,
                "message": f"browser-use会话已启动: {task}"
            }
    
    def check_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """检查会话的URL变化。"""
        with self._manager_lock:
            # 确定要检查的会话
            if session_id is None:
                session_id = self.active_session_id
            
            if not session_id or session_id not in self.sessions:
                raise ValueError(f"会话 '{session_id}' 不存在")
            
            session = self.sessions[session_id]
            
            try:
                result = session.check()
                result["message"] = f"检查会话 {session_id} 完成"
            except Exception as e:
                raise RuntimeError(f"检查会话失败: {e}") from e
            else:
                return result
    
    def get_active_session(self) -> Optional[BrowserUseInstance]:
        """获取活动会话。"""
        with self._manager_lock:
            if self.active_session_id and self.active_session_id in self.sessions:
                return self.sessions[self.active_session_id]
            return None
    
    def get_session_status(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """获取会话状态。"""
        with self._manager_lock:
            if session_id is None:
                session_id = self.active_session_id
            
            if not session_id or session_id not in self.sessions:
                raise ValueError(f"会话 '{session_id}' 不存在")
            
            session = self.sessions[session_id]
            return session.get_status()
    
    
    def list_sessions(self) -> Dict[str, Any]:
        """列出所有会话。"""
        with self._manager_lock:
            sessions_info = {}
            for session_id, session in self.sessions.items():
                sessions_info[session_id] = {
                    "task": session.task,
                    "is_running": session.is_running,
                    "start_time": session.start_time,
                    "running_time": time.time() - session.start_time,
                    "total_changes": len(session.url_changes),
                    "is_active": session_id == self.active_session_id
                }
            
            return {
                "sessions": sessions_info,
                "total_sessions": len(self.sessions),
                "active_session_id": self.active_session_id,
                "message": f"共 {len(self.sessions)} 个会话"
            }


def get_browser_use_manager() -> BrowserUseManager:
    """获取browser-use管理器单例（参考tab_manager.py的get_browser_tab_manager）。"""
    return BrowserUseManager()