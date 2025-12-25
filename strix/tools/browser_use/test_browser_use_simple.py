"""browser-use自动化工具。"""

import asyncio
import logging
import os
import threading
import traceback
from typing import Any, Dict

# 配置日志到终端
logger = logging.getLogger('browser_use')
logger.setLevel(logging.DEBUG)

# 清除现有处理器
if logger.handlers:
    logger.handlers.clear()

# 创建终端处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# 创建格式化器 - 简化格式便于终端查看
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 添加处理器到日志记录器
logger.addHandler(console_handler)

# 确保日志传播
logger.propagate = True

# 立即写入一条测试日志
logger.debug("=" * 60)
logger.debug("browser_use 日志记录器初始化完成")


async def _on_step_callback_async(agent):
    """异步生命周期钩子回调函数，在每个步骤结束时调用。

    Args:
        agent: Agent实例
    """
    try:
        # 获取所有四种数据
        thoughts = agent.history.model_thoughts()
        outputs = agent.history.model_outputs()
        actions = agent.history.model_actions()
        content = agent.history.extracted_content()

        # 详细记录到日志
        logger.info(f"=== _on_step_callback_async 被调用 ===")
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

    except Exception as e:
        logger.error(f"_on_step_callback_async 错误: {e}")
        logger.error(f"错误详情: {traceback.format_exc()}")


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

        # 设置 NO_PROXY 环境变量，确保本地和 LLM 通信不受代理影响
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
            add_schema_to_system_prompt=True
        )
        logger.info(f"LLM实例创建成功: {type(llm)}")

        browser = Browser(cdp_url="http://127.0.0.1:9222")
        logger.info(f"Browser实例创建成功，CDP URL: http://127.0.0.1:9222")

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            use_vision=False,
            #validate_output=False,
            #extend_system_message=extend_system_message
        )
        logger.info(f"Agent实例创建成功: {type(agent)}")

        # 使用线程启动异步任务（不阻塞当前调用）
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
        
        # 直接使用异步回调函数
        await agent.run(on_step_end=_on_step_callback_async)
        
        logger.info("agent.run() 执行完成")
        logger.info(f"任务执行完成")
            
    except Exception as e:
        logger.error(f"_run_agent_async 执行失败: {e}")
        logger.error(f"错误详情: {traceback.format_exc()}")


def main():
    """主函数，可以直接调用运行browser-use任务"""
    import sys
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法: python browser_use_tool.py \"任务描述\"")
        print("示例: python browser_use_tool.py \"打开百度并搜索Python\"")
        sys.exit(1)
    
    # 获取任务描述
    task = sys.argv[1]
    
    # 运行任务
    logger.info("=" * 60)
    logger.info("开始执行 browser-use 任务")
    logger.info(f"任务: {task}")
    logger.info("=" * 60)
    
    result = browser_use(task)
    
    # 输出结果
    logger.info(f"任务启动结果: {result}")
    
    # 如果是在后台线程中运行，等待线程结束
    if result.get("status") == "started":
        logger.info("任务已在后台运行，等待执行完成...")
        # 这里可以添加等待逻辑，或者让程序继续运行
        # 由于是后台线程，主线程需要保持运行
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("用户中断，程序退出")


if __name__ == "__main__":
    main()