"""browser-use自动化工具。"""

import asyncio
import logging
import os
import threading
import traceback
from typing import Any, Dict

from strix.tools.registry import register_tool


# 优化提示词指南
ENHANCED_GUIDE = """
--- 通用操作指南 ---

### 【登录任务指南】
当进行登录操作时，请遵循以下步骤：

1. 如果可以选择登录方式，选择密码登录方式
2. 检查是否需要登录，进行登录
    - 如果需要，找到用户名输入框，输入提供的用户名
    - 找到密码输入框，输入提供的密码
    - 【重要】有图片验证码时，识别并输入验证码
    - 登录表单
3. 如果"登录"按钮不可点击：
    - 检查是否存在 "同意协议 / 同意条款 / 接受政策" 等选项
    - 如果存在，勾选该选项后再次尝试登录
    - 如果按钮已可点击，说明协议已勾选，无需重复
4. 如果不需要登录，直接跳过登录步骤

注意事项：不要使用search功能，使用go_to_url进行url访问；根据url访问，不要随意修改域名


### 【含验证码登录指南】
当登录需要验证码时，请遵循以下步骤：

1. 如果有登录方式可选，优先选择"密码登录"方式
2. 检查是否需要登录，进行登录
    - 如果需要，找到用户名输入框并输入，输入提供的用户名(如有)
    - 找到密码输入框并输入提供的密码(如有)
    - 如果页面存在图片验证码，识别后输入验证码(如有)
    - 提交登录表单
3. 如果"登录"按钮不可点击：
    - 检查是否存在 "同意协议 / 同意条款 / 接受政策" 等选项
    - 如果存在，勾选该选项后再次尝试登录
    - 如果按钮已可点击，说明协议已勾选，无需重复
4. 如果页面跳转后要求额外的验证码认证（如短信验证码 / 邮件验证码等），输入提供的验证码(如有)
5. 如果不需要登录，直接跳过登录步骤

注意事项：严禁使用 search 功能，只能使用 go_to_url 访问网站；根据上面提供的网站访问，不要随意修改域名；多因子认证时必须使用步骤 4 中的验证码进行提交

### 【探索页面功能任务指南】
任务目标：触发所有模块下所有与服务端发生数据交互的功能，逐个点击所有功能模块，当确认所有功能都点击过后，完成任务。

核心规则：
- 标有`勿删`信息的，请不要删除
- 直接复用表单里默认值即可，非必要值也不用填写，目的为了快速完成功能触发
- 多个样式相同的按钮/条目（如分页列表中的卡片项），只需选择一个代表性条目进行触发，不要操作分页器

操作步骤：
1. 点击功能模块上的所有链接，访问每个链接指向的页面
2. 如遇页面跳转到其它模块，需自动回退
3. 展开所有可展开的二级或三级菜单
4. 点击所有可点击的按钮和链接，填写并提交页面上的所有表单：
   - 如表单有默认数据，直接提交
   - 否则填入合理的测试数据后提交

禁止操作（必须跳过）：
- 不同域名的链接或表单
- 退出登录按钮
- help/帮助、操作指南等相关接口
- 静态资源链接
- 破坏性操作（重置系统、清空数据、回滚系统、修改密码、配置网卡、配置网络等）


注意事项：
- 检查表单字段是selector类型时，先点击select输入框，然后从可点击index里选择预设内容
- 不要使用search功能，使用go_to_url进行url访问
- 无需验证响应结果，触发一次即算完成
- 如果退出需要重新登录：输入账号密码即可，不要重复再点击所有功能
- 失败超过6次搞不定，任务完成结束


### 【模块导航任务指南】
任务目标：逐个点击所有功能模块


操作要求：
1. 点击前检查目标元素，确认目标元素是可见的、可交互的，且没有被遮挡
2. 点击完成后，检查页面是否发生了变化：
   - 是否出现新的弹窗/下拉菜单
   - 是否跳转到指定模块/页面
   - 是否有元素变为 .active、.selected 状态
   - 是否 URL 或内容区域发生更新
3. 模块必须被实际点击，判断条件是触发高亮、激活状态等，否则任务不算完成

--- 操作指南结束 ---
"""


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

        # 拼接优化指南到原始 task
        enhanced_task = f"{task}\n\n{ENHANCED_GUIDE}"
        logger.info(f"优化后的任务描述长度: {len(enhanced_task)}")

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
            task=enhanced_task,  # 使用增强后的任务描述
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
