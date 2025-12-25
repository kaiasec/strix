"""browser-use自动化工具。"""

import asyncio
import logging
import os
import threading
import traceback
from typing import Any, Dict

from strix.tools.registry import register_tool

# 创建专门的日志记录器
logger = logging.getLogger('browser_use')
logger.setLevel(logging.DEBUG)

# 清除现有处理器
if logger.handlers:
    logger.handlers.clear()

# 创建文件处理器 - 使用追加模式确保日志不会丢失
file_handler = logging.FileHandler('/tmp/browser_use.log', mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 添加处理器到日志记录器
logger.addHandler(file_handler)

# 确保日志传播
logger.propagate = True

# 立即写入一条测试日志
logger.debug("=" * 60)
logger.debug("browser_use 日志记录器初始化完成")


async def _on_step_callback(agent):
    """内部生命周期钩子回调函数，在每个步骤结束时调用。

    Args:
        agent: Agent实例
    """
    try:
        # 获取所有四种数据
        thoughts = agent.history.model_thoughts()
        outputs = agent.history.model_outputs()
        actions = agent.history.model_actions()
        content = agent.history.extracted_content()

        # 详细记录到日志文件
        logger.info(f"=== _on_step_callback 被调用 ===")
        logger.info(f"model_thoughts 数量: {len(thoughts)}")
        logger.info(f"model_outputs 数量: {len(outputs)}")
        logger.info(f"model_actions 数量: {len(actions)}")
        logger.info(f"extracted_content 数量: {len(content)}")

        # 安全地记录最新数据，处理可能的非字符串类型
        if thoughts:
            latest_thought = thoughts[-1]
            thought_str = str(latest_thought) if not isinstance(latest_thought, str) else latest_thought
            logger.info(f"最新模型思考: {thought_str[:200]}...")
        if outputs:
            latest_output = outputs[-1]
            output_str = str(latest_output) if not isinstance(latest_output, str) else latest_output
            logger.info(f"最新模型输出: {output_str[:200]}...")
        if actions:
            latest_action = actions[-1]
            action_str = str(latest_action) if not isinstance(latest_action, str) else latest_action
            logger.info(f"最新执行动作: {action_str[:200]}...")
        if content:
            latest_content = content[-1]
            content_str = str(latest_content) if not isinstance(latest_content, str) else latest_content
            logger.info(f"最新提取内容: {content_str[:200]}...")

        # 数据已经通过日志记录，终端渲染由TUI的render系统处理

    except Exception as e:
        logger.error(f"_on_step_callback 错误: {e}")
        logger.error(f"错误详情: {traceback.format_exc()}")


@register_tool()
def browser_use(task: str) -> dict[str, Any]:
    """执行browser-use自动化任务。

    Args:
        task: 任务描述

    Returns:
        包含任务ID和执行状态的字典
    """
    try:
        logger.info(f"=== browser_use 函数被调用 ===")
        logger.info(f"任务描述: {task}")

        from browser_use import Agent, Browser
        from browser_use.llm import ChatOpenAI
        #from langchain_openai import ChatOpenAI
        
        logger.info("成功导入 browser_use 模块")

        # 设置 NO_PROXY 环境变量，确保本地和 LLM 通信不受 caido 代理影响
        #os.environ['NO_PROXY'] = '127.0.0.1,localhost,api.deepseek.com,open.bigmodel.cn,api.silra.cn'
        os.environ['NO_PROXY'] = '*'

        model = os.getenv("STRIX_LLM")
        model = model.split('/')[-1]
        base_url = os.getenv("LLM_API_BASE")
        api_key = os.getenv("LLM_API_KEY")

        logger.info(f"LLM配置 - model: {model}, base_url: {base_url}, api_key前6位: {api_key[:6]}...")

        llm = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            dont_force_structured_output=True,
            add_schema_to_system_prompt=True,
            max_completion_tokens=4096,
        )
        logger.info(f"LLM实例创建成功: {type(llm)}")

        browser = Browser(cdp_url="http://127.0.0.1:9222")
        logger.info(f"Browser实例创建成功，CDP URL: http://127.0.0.1:9222")


        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            use_vision=False,
            llm_timeout=600,
	        max_failures=6
        )
        logger.info(f"Agent实例创建成功: {type(agent)}")

        # 使用线程启动异步任务（不阻塞当前调用）
        import threading

        def _run_in_thread():
            """在线程中运行异步任务"""
            try:
                # 创建新的事件循环
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)

                # 运行异步任务
                new_loop.run_until_complete(_run_agent_async(agent))
            except Exception as e:
                logger.error(f"线程中运行任务失败: {e}")

        # 启动后台线程
        thread = threading.Thread(target=_run_in_thread, daemon=True)
        thread.start()
        logger.info(f"在后台线程中启动异步任务")

        return {
            "status": "started",
            "task": task,
            "message": "浏览器自动化任务已启动",
        }

    except ImportError as e:
        logger.error(f"导入失败: {e}")
        logger.error(f"导入失败详情: {traceback.format_exc()}")
        return {"error": f"导入失败: {e}", "status": "error"}
    except Exception as e:
        logger.error(f"执行失败: {e}")
        logger.error(f"执行失败详情: {traceback.format_exc()}")
        return {"error": f"执行失败: {e}", "status": "error"}


async def _run_agent_async(agent):
    """异步运行Agent。"""
    try:
        logger.info(f"_run_agent_async 开始执行")
        
        logger.info("开始执行 agent.run()...")
        await agent.run(on_step_end=_on_step_callback)
        logger.info("agent.run() 执行完成")
        
        logger.info(f"任务执行完成")
            
    except Exception as e:
        logger.error(f"_run_agent_async 执行失败: {e}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        
        logger.info(f"错误已记录")
