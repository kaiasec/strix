"""browser-use会话实例，管理独立任务执行。"""

import asyncio
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, cast

# 设置 NO_PROXY 环境变量，确保本地和 LLM 通信不受 caido 代理影响
os.environ['NO_PROXY'] = '127.0.0.1,localhost,api.deepseek.com'

logger = logging.getLogger(__name__)


class BrowserUseInstance:
    """browser-use会话实例，管理独立任务执行和URL变化检测。"""
    
    def __init__(self, session_id: str, task: str, max_steps: int = 50) -> None:
        self.session_id = session_id
        self.task = task
        self.max_steps = max_steps
        self.start_time = time.time()
        
        self.is_running = True
        self.url_changes: List[Dict[str, Any]] = []
        self.last_check_time = time.time()
        self._stop_flag = False
        
        self._execution_lock = threading.Lock()
        
        # 持久化事件循环
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_event_loop()
        
        # 启动任务
        self._run_task()
    
    def _start_event_loop(self) -> None:
        """启动持久化事件循环（参考browser_instance.py第37-50行）。"""
        def run_loop() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        
        # 等待事件循环初始化
        while self._loop is None:
            threading.Event().wait(0.01)
    
    def _run_async(self, coro: Any) -> Dict[str, Any]:
        """在持久化事件循环中执行协程（参考browser_instance.py第51-56行）。"""
        if not self._loop or not self.is_running:
            raise RuntimeError("Browser-use实例未运行")
        
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return cast("Dict[str, Any]", future.result(timeout=30))
    
    def _run_task(self) -> None:
        """启动browser-use任务。"""
        try:
            self._run_async(self._run_browser_use_task())
        except Exception as e:
            logger.error(f"启动browser-use任务失败: {e}")
            self.is_running = False
    
    async def _run_browser_use_task(self) -> None:
        """运行browser-use任务。"""
        try:
            from browser_use import Agent, Browser
            from browser_use.llm import ChatDeepSeek
        except ImportError as e:
            logger.error(f"导入browser-use失败: {e}")
            self.is_running = False
            return
        
        import os
        api_key = os.getenv('DEEPSEEK_API_KEY', 'sk-35c22abdef0a493a9a120c4395fd5303')
        if not api_key:
            logger.error("需要DEEPSEEK_API_KEY环境变量")
            self.is_running = False
            return
        
        try:
            llm = ChatDeepSeek(
                base_url='https://api.deepseek.com/v1',
                model='deepseek-chat',
                api_key=api_key
            )
            
            browser = Browser(cdp_url="http://127.0.0.1:9222")
            
            async def on_step(agent: Agent) -> None:
                """检测URL变化。"""
                if self._stop_flag:
                    return
                
                try:
                    urls = agent.history.urls()
                    current = urls[-1] if urls else None
                    previous = urls[-2] if len(urls) >= 2 else None
                    
                    if current != previous:
                        change = {
                            "step": len(agent.history),
                            "from": previous,
                            "to": current,
                            "timestamp": time.time(),
                            "session_id": self.session_id
                        }
                        self.url_changes.append(change)
                        logger.info(f"[{self.session_id}] URL变化: {previous or '初始'} -> {current}")
                except Exception as e:
                    logger.error(f"记录URL变化出错: {e}")
            
            logger.info(f"[{self.session_id}] 开始任务: {self.task}")
            agent = Agent(task=self.task, llm=llm, browser=browser, max_steps=self.max_steps)
            await agent.run(on_step_end=on_step)
            
            logger.info(f"[{self.session_id}] 任务完成")
            
        except Exception as e:
            logger.error(f"[{self.session_id}] 执行出错: {e}")
        finally:
            self.is_running = False
    
    def check(self) -> Dict[str, Any]:
        """检查URL变化。"""
        with self._execution_lock:
            if not self.is_running:
                raise RuntimeError(f"会话 {self.session_id} 未运行")
            
            current_time = time.time()
            last_check = self.last_check_time
            
            # 获取新变化
            new_changes = [c for c in self.url_changes if c["timestamp"] > last_check]
            
            # 更新检查时间
            self.last_check_time = current_time
            
            result = {
                "session_id": self.session_id,
                "task": self.task,
                "running_time": current_time - self.start_time,
                "new_changes": new_changes,
                "new_changes_count": len(new_changes),
                "total_changes": len(self.url_changes),
                "last_check": last_check,
                "current_check": current_time,
                "is_running": self.is_running
            }
            
            # 添加建议信息
            if new_changes:
                result["message"] = f"发现 {len(new_changes)} 个新URL变化"
                result["suggestion"] = "Strix应考虑调用list_requests分析这些URL"
            else:
                result["message"] = "暂无新URL变化"
                result["suggestion"] = "browser-use仍在运行中，继续监控"
            
            return result
    
    def stop(self) -> None:
        """停止会话。"""
        with self._execution_lock:
            self._stop_flag = True
            self.is_running = False
    
    def get_status(self) -> Dict[str, Any]:
        """获取会话状态。"""
        with self._execution_lock:
            return {
                "session_id": self.session_id,
                "task": self.task,
                "is_running": self.is_running,
                "start_time": self.start_time,
                "running_time": time.time() - self.start_time,
                "total_changes": len(self.url_changes),
                "last_check_time": self.last_check_time
            }