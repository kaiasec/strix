from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar, overload

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionContentPartTextParam
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.shared.chat_model import ChatModel
from openai.types.shared_params.reasoning_effort import ReasoningEffort
from openai.types.shared_params.response_format_json_schema import JSONSchema, ResponseFormatJSONSchema
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError, ModelRateLimitError
from browser_use.llm.messages import BaseMessage
from browser_use.llm.openai.serializer import OpenAIMessageSerializer
from browser_use.llm.schema import SchemaOptimizer
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage

T = TypeVar('T', bound=BaseModel)


@dataclass
class ChatOpenAI(BaseChatModel):
	"""
	A wrapper around AsyncOpenAI that implements the BaseLLM protocol.

	This class accepts all AsyncOpenAI parameters while adding model
	and temperature parameters for the LLM interface (if temperature it not `None`).
	"""

	# Model configuration
	model: ChatModel | str

	# Model params
	temperature: float | None = 0.2
	frequency_penalty: float | None = 0.3  # this avoids infinite generation of \t for models like 4.1-mini
	reasoning_effort: ReasoningEffort = 'low'
	seed: int | None = None
	service_tier: Literal['auto', 'default', 'flex', 'priority', 'scale'] | None = None
	top_p: float | None = None
	add_schema_to_system_prompt: bool = False  # Add JSON schema to system prompt instead of using response_format
	dont_force_structured_output: bool = False  # If True, the model will not be forced to output a structured output
	remove_min_items_from_schema: bool = (
		False  # If True, remove minItems from JSON schema (for compatibility with some providers)
	)
	remove_defaults_from_schema: bool = (
		False  # If True, remove default values from JSON schema (for compatibility with some providers)
	)

	# Client initialization parameters
	api_key: str | None = None
	organization: str | None = None
	project: str | None = None
	base_url: str | httpx.URL | None = None
	websocket_base_url: str | httpx.URL | None = None
	timeout: float | httpx.Timeout | None = None
	max_retries: int = 5  # Increase default retries for automation reliability
	default_headers: Mapping[str, str] | None = None
	default_query: Mapping[str, object] | None = None
	http_client: httpx.AsyncClient | None = None
	_strict_response_validation: bool = False
	max_completion_tokens: int | None = 4096
	reasoning_models: list[ChatModel | str] | None = field(
		default_factory=lambda: [
			'o4-mini',
			'o3',
			'o3-mini',
			'o1',
			'o1-pro',
			'o3-pro',
			'gpt-5',
			'gpt-5-mini',
			'gpt-5-nano',
		]
	)

	# Static
	@property
	def provider(self) -> str:
		return 'openai'

	def _get_client_params(self) -> dict[str, Any]:
		"""Prepare client parameters dictionary."""
		# Define base client params
		base_params = {
			'api_key': self.api_key,
			'organization': self.organization,
			'project': self.project,
			'base_url': self.base_url,
			'websocket_base_url': self.websocket_base_url,
			'timeout': self.timeout,
			'max_retries': self.max_retries,
			'default_headers': self.default_headers,
			'default_query': self.default_query,
			'_strict_response_validation': self._strict_response_validation,
		}

		# Create client_params dict with non-None values
		client_params = {k: v for k, v in base_params.items() if v is not None}

		# Add http_client if provided
		if self.http_client is not None:
			client_params['http_client'] = self.http_client

		return client_params

	def get_client(self) -> AsyncOpenAI:
		"""
		Returns an AsyncOpenAI client.

		Returns:
			AsyncOpenAI: An instance of the AsyncOpenAI client.
		"""
		client_params = self._get_client_params()
		return AsyncOpenAI(**client_params)

	@property
	def name(self) -> str:
		return str(self.model)

	def _get_usage(self, response: ChatCompletion) -> ChatInvokeUsage | None:
		if response.usage is not None:
			completion_tokens = response.usage.completion_tokens
			completion_token_details = response.usage.completion_tokens_details
			if completion_token_details is not None:
				reasoning_tokens = completion_token_details.reasoning_tokens
				if reasoning_tokens is not None:
					completion_tokens += reasoning_tokens

			usage = ChatInvokeUsage(
				prompt_tokens=response.usage.prompt_tokens,
				prompt_cached_tokens=response.usage.prompt_tokens_details.cached_tokens
				if response.usage.prompt_tokens_details is not None
				else None,
				prompt_cache_creation_tokens=None,
				prompt_image_tokens=None,
				# Completion
				completion_tokens=completion_tokens,
				total_tokens=response.usage.total_tokens,
			)
		else:
			usage = None

		return usage

	@overload
	async def ainvoke(
		self, messages: list[BaseMessage], output_format: None = None, **kwargs: Any
	) -> ChatInvokeCompletion[str]: ...

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: type[T], **kwargs: Any) -> ChatInvokeCompletion[T]: ...

	async def ainvoke(
		self, messages: list[BaseMessage], output_format: type[T] | None = None, **kwargs: Any
	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
		"""
		Invoke the model with the given messages.

		Args:
			messages: List of chat messages
			output_format: Optional Pydantic model class for structured output

		Returns:
			Either a string response or an instance of output_format
		"""

		openai_messages = OpenAIMessageSerializer.serialize_messages(messages)

		try:
			model_params: dict[str, Any] = {}

			if self.temperature is not None:
				model_params['temperature'] = self.temperature

			if self.frequency_penalty is not None:
				model_params['frequency_penalty'] = self.frequency_penalty

			if self.max_completion_tokens is not None:
				model_params['max_completion_tokens'] = self.max_completion_tokens

			if self.top_p is not None:
				model_params['top_p'] = self.top_p

			if self.seed is not None:
				model_params['seed'] = self.seed

			if self.service_tier is not None:
				model_params['service_tier'] = self.service_tier

			if self.reasoning_models and any(str(m).lower() in str(self.model).lower() for m in self.reasoning_models):
				model_params['reasoning_effort'] = self.reasoning_effort
				model_params.pop('temperature', None)
				model_params.pop('frequency_penalty', None)

			if output_format is None:
				# Return string response
				response = await self.get_client().chat.completions.create(
					model=self.model,
					messages=openai_messages,
					**model_params,
				)

				usage = self._get_usage(response)
				return ChatInvokeCompletion(
					completion=response.choices[0].message.content or '',
					usage=usage,
					stop_reason=response.choices[0].finish_reason if response.choices else None,
				)

			else:
				response_format: JSONSchema = {
					'name': 'agent_output',
					'strict': True,
					'schema': SchemaOptimizer.create_optimized_json_schema(
						output_format,
						remove_min_items=self.remove_min_items_from_schema,
						remove_defaults=self.remove_defaults_from_schema,
					),
				}

				# Add JSON schema to system prompt if requested
				if self.add_schema_to_system_prompt and openai_messages and openai_messages[0]['role'] == 'system':
					schema_text = f'\n<json_schema>\n{response_format}\n</json_schema>'
					if isinstance(openai_messages[0]['content'], str):
						openai_messages[0]['content'] += schema_text
					elif isinstance(openai_messages[0]['content'], Iterable):
						openai_messages[0]['content'] = list(openai_messages[0]['content']) + [
							ChatCompletionContentPartTextParam(text=schema_text, type='text')
						]

				if self.dont_force_structured_output and 'glm' in str(self.model).lower():
					response = await self.get_client().chat.completions.create(
						model=self.model,
						messages=openai_messages,
						response_format={"type": "json_object"},
						**model_params,
					)
				elif self.dont_force_structured_output:
					response = await self.get_client().chat.completions.create(
						model=self.model,
						messages=openai_messages,
						**model_params,
					)
				else:
					# Return structured response
					response = await self.get_client().chat.completions.create(
						model=self.model,
						messages=openai_messages,
						response_format=ResponseFormatJSONSchema(json_schema=response_format, type='json_schema'),
						**model_params,
					)

				if response.choices[0].message.content is None:
					raise ModelProviderError(
						message='Failed to parse structured output from model response',
						status_code=500,
						model=self.name,
					)

				usage = self._get_usage(response)

				parsed = output_format.model_validate_json(response.choices[0].message.content)

				return ChatInvokeCompletion(
					completion=parsed,
					usage=usage,
					stop_reason=response.choices[0].finish_reason if response.choices else None,
				)

		except RateLimitError as e:
			raise ModelRateLimitError(message=e.message, model=self.name) from e

		except APIConnectionError as e:
			raise ModelProviderError(message=str(e), model=self.name) from e

		except APIStatusError as e:
			raise ModelProviderError(message=e.message, status_code=e.status_code, model=self.name) from e

		# except Exception as e:
		# 	# ============ 添加详细的错误日志 ============
		# 	import traceback
		# 	import json
			
		# 	# 创建或获取logger
		# 	import logging
		# 	logger = logging.getLogger(__name__)
			
		# 	# 记录详细的错误信息
		# 	logger.error("💥 ====== CRITICAL ERROR IN LLM RESPONSE PARSING ======")
		# 	logger.error(f"Error type: {type(e).__name__}")
		# 	logger.error(f"Error message: {str(e)}")
		# 	logger.error(f"Model: {self.name}")
			
		# 	# 检查是否是Pydantic验证错误
		# 	if "validation" in str(e).lower() or "pydantic" in str(e).lower():
		# 		logger.error("🔍 This appears to be a Pydantic validation error")
				
		# 	# 记录响应内容（如果response存在）
		# 	if 'response' in locals() and response:
		# 		logger.error(f"Response ID: {response.id}")
		# 		logger.error(f"Response model: {response.model}")
		# 		logger.error(f"Finish reason: {response.choices[0].finish_reason if response.choices else 'N/A'}")
				
		# 		if response.choices and response.choices[0].message:
		# 			raw_content = response.choices[0].message.content
		# 			logger.error("📋 RAW RESPONSE CONTENT:")
		# 			logger.error(f"{raw_content}")
					
		# 			# 尝试解析JSON来查看结构
		# 			if raw_content:
		# 				logger.error(f"Content length: {len(raw_content)} characters")
		# 				try:
		# 					parsed = json.loads(raw_content)
		# 					logger.error("✅ Content is valid JSON")
		# 					logger.error("📊 JSON STRUCTURE (pretty):")
		# 					logger.error(json.dumps(parsed, indent=2, ensure_ascii=False))
							
		# 					# 分析结构问题
		# 					logger.error("🔍 STRUCTURE ANALYSIS:")
		# 					if isinstance(parsed, dict):
		# 						for key, value in parsed.items():
		# 							logger.error(f"  Key: {key}, Type: {type(value).__name__}")
		# 							if key == 'action' and isinstance(value, list) and value:
		# 								for i, action in enumerate(value):
		# 									logger.error(f"    Action[{i}]: {type(action).__name__}")
		# 									if isinstance(action, dict):
		# 										logger.error(f"      Keys: {list(action.keys())}")
		# 										for k, v in action.items():
		# 											logger.error(f"        {k}: {type(v).__name__}")
		# 											if k == 'screenshot':
		# 												logger.error(f"        ⚠️ WARNING: Found 'screenshot' field with value: {v}")
		# 				except json.JSONDecodeError as je:
		# 					logger.error(f"❌ Content is NOT valid JSON: {je}")
		# 					logger.error(f"First 500 chars: {raw_content[:500]}")
		# 			else:
		# 				logger.error("❌ Response content is None or empty")
		# 	else:
		# 		logger.error("❌ No response object available for analysis")
			
		# 	# 记录完整的堆栈跟踪
		# 	logger.error("📝 FULL TRACEBACK:")
		# 	logger.error(traceback.format_exc())
		# 	logger.error("💥 ====== END ERROR LOG ======")
		# 	# ============ 添加结束 ============
		# 	raise ModelProviderError(message=str(e), model=self.name) from e


		except Exception as e:
			# # ============ 添加详细的错误日志 ============
			# import traceback
			# import json
			
			# # 创建或获取logger
			# import logging
			# logger = logging.getLogger(__name__)
			
			# # 记录详细的错误信息
			# logger.error("💥 ====== CRITICAL ERROR IN LLM RESPONSE PARSING ======")
			# logger.error(f"Error type: {type(e).__name__}")
			# logger.error(f"Error message: {str(e)}")
			# logger.error(f"Model: {self.name}")
			
			# # ============ 1. 分析发送给LLM的原始消息 ============
			# logger.error("🔍 ====== ANALYSIS OF INPUT MESSAGES TO LLM ======")
			# logger.error(f"Total messages sent to LLM: {len(messages)}")
			
			# for i, msg in enumerate(messages):
			# 	msg_type = msg.__class__.__name__
				
			# 	# 获取消息内容
			# 	content = ""
			# 	if hasattr(msg, 'content'):
			# 		content = str(msg.content)
			# 	elif hasattr(msg, 'text'):
			# 		content = str(msg.text)
			# 	else:
			# 		content = str(msg)
				
			# 	# 显示基本信息
			# 	logger.error(f"Message[{i}] - Type: {msg_type}")
				
			# 	# 如果是系统消息或太长的消息，显示摘要
			# 	if msg_type == 'SystemMessage' or len(content) > 500:
			# 		# 显示前200个字符和后100个字符
			# 		preview = content[:200]
			# 		if len(content) > 300:
			# 			preview += f"...[{len(content)-300} chars]..." + content[-100:]
			# 		logger.error(f"  Content preview: {preview}")
					
			# 		# 检查是否有screenshot相关内容
			# 		if 'screenshot' in content.lower():
			# 			logger.error(f"  ⚠️ Contains 'screenshot' keyword")
						
			# 			# 查找具体的JSON格式
			# 			import re
			# 			screenshot_patterns = re.findall(r'\{[^{}]*"screenshot"[^{}]*\}', content)
			# 			if screenshot_patterns:
			# 				for pattern in screenshot_patterns:
			# 					logger.error(f"  ❌ Found screenshot pattern: {pattern}")
			# 	else:
			# 		# 显示完整内容
			# 		logger.error(f"  Content: {content}")
			
			# # ============ 2. 分析序列化后的OpenAI消息 ============
			# logger.error("🔍 ====== SERIALIZED OPENAI MESSAGES ======")
			# try:
			# 	serialized = OpenAIMessageSerializer.serialize_messages(messages)
			# 	for i, msg in enumerate(serialized):
			# 		role = msg.get('role', 'unknown')
			# 		content = msg.get('content', '')
			# 		if isinstance(content, str):
			# 			preview = content[:150] + "..." if len(content) > 150 else content
			# 		elif isinstance(content, list):
			# 			preview = f"[List with {len(content)} items]"
			# 			# 检查列表中是否有screenshot
			# 			for item in content:
			# 				if isinstance(item, dict) and 'text' in item:
			# 					if 'screenshot' in item['text'].lower():
			# 						logger.error(f"  ⚠️ Serialized message[{i}] contains 'screenshot' in text")
			# 		else:
			# 			preview = str(content)[:150] + "..."
					
			# 		logger.error(f"  [{i}] role={role}: {preview}")
			# except Exception as serialize_error:
			# 	logger.error(f"  Failed to serialize messages: {serialize_error}")
			
			# # ============ 3. 输出格式信息 ============
			# if output_format is not None:
			# 	logger.error("🔍 ====== OUTPUT FORMAT SCHEMA ======")
			# 	try:
			# 		schema = output_format.model_json_schema()
			# 		logger.error(f"  Output format: {output_format.__name__}")
					
			# 		# 特别查看action字段的定义
			# 		if 'properties' in schema and 'action' in schema['properties']:
			# 			action_def = schema['properties']['action']
			# 			logger.error("  Action field definition:")
						
			# 			# 显示简洁的action定义
			# 			if 'items' in action_def and 'anyOf' in action_def['items']:
			# 				logger.error(f"    Type: List of {len(action_def['items']['anyOf'])} possible actions")
			# 				for j, action_type in enumerate(action_def['items']['anyOf']):
			# 					if '$ref' in action_type:
			# 						logger.error(f"    [{j}] $ref: {action_type['$ref']}")
			# 					elif 'properties' in action_type:
			# 						action_keys = list(action_type['properties'].keys())
			# 						logger.error(f"    [{j}] Keys: {action_keys}")
			# 	except Exception as schema_error:
			# 		logger.error(f"  Failed to get schema: {schema_error}")
			
			# # ============ 4. 检查是否是Pydantic验证错误 ============
			# error_str = str(e).lower()
			# if "validation" in error_str or "pydantic" in error_str:
			# 	logger.error("🔍 This is a Pydantic validation error")
				
			# 	# 分析常见的验证错误类型
			# 	if "extra_forbidden" in error_str:
			# 		logger.error("❌ Error type: EXTRA_FORBIDDEN - Model received unexpected fields")
			# 	if "missing" in error_str:
			# 		logger.error("❌ Error type: MISSING - Required fields are missing")
				
			# 	# 特别处理screenshot相关错误
			# 	if "screenshot" in error_str:
			# 		logger.error("🚨 Related to 'screenshot' field")
			# 		logger.error("💡 Solution: Use {'evaluate': {'screenshot': true, 'thought': '...'}} instead of {'screenshot': {}}")
			
			# # ============ 5. 记录响应内容（如果response存在） ============
			# if 'response' in locals() and response:
			# 	logger.error("🔍 ====== LLM RESPONSE ANALYSIS ======")
			# 	logger.error(f"Response ID: {response.id}")
			# 	logger.error(f"Response model: {response.model}")
			# 	logger.error(f"Finish reason: {response.choices[0].finish_reason if response.choices else 'N/A'}")
				
			# 	if response.choices and response.choices[0].message:
			# 		raw_content = response.choices[0].message.content
			# 		if raw_content:
			# 			logger.error(f"Content length: {len(raw_content)} characters")
			# 			logger.error("📋 RAW RESPONSE CONTENT:")
			# 			logger.error(f"{raw_content}")
						
			# 			# 尝试解析JSON来查看结构
			# 			try:
			# 				parsed = json.loads(raw_content)
			# 				logger.error("✅ Content is valid JSON")
			# 				logger.error("📊 JSON STRUCTURE (pretty):")
			# 				logger.error(json.dumps(parsed, indent=2, ensure_ascii=False))
							
			# 				# 分析结构问题
			# 				logger.error("🔍 STRUCTURE ANALYSIS:")
			# 				if isinstance(parsed, dict):
			# 					for key, value in parsed.items():
			# 						value_type = type(value).__name__
			# 						logger.error(f"  Key: {key}, Type: {value_type}")
									
			# 						if key == 'action' and isinstance(value, list):
			# 							logger.error(f"  Action list has {len(value)} items")
			# 							for i, action in enumerate(value):
			# 								if isinstance(action, dict):
			# 									action_keys = list(action.keys())
			# 									logger.error(f"    Action[{i}]: {action_keys}")
												
			# 									# 检查是否有screenshot
			# 									if 'screenshot' in action_keys:
			# 										logger.error(f"    ⚠️ WARNING: Action[{i}] contains 'screenshot' key")
			# 										logger.error(f"      Value: {action['screenshot']}")
			# 										logger.error(f"      💡 Should be part of 'evaluate' action")
			# 			except json.JSONDecodeError as je:
			# 				logger.error(f"❌ Content is NOT valid JSON: {je}")
			# 				logger.error(f"First 500 chars: {raw_content[:500]}")
			# 		else:
			# 			logger.error("❌ Response content is None or empty")
			# else:
			# 	logger.error("❌ No response object available for analysis")
			
			# # ============ 6. 记录模型参数和配置 ============
			# logger.error("🔍 ====== MODEL CONFIGURATION ======")
			# logger.error(f"Model: {self.model}")
			# logger.error(f"Temperature: {self.temperature}")
			# logger.error(f"Output format specified: {output_format is not None}")
			# logger.error(f"Force structured output: {not self.dont_force_structured_output}")
			# logger.error(f"Add schema to prompt: {self.add_schema_to_system_prompt}")
			
			# # ============ 7. 记录完整的堆栈跟踪 ============
			# logger.error("📝 ====== FULL TRACEBACK ======")
			# logger.error(traceback.format_exc())
			
			# # ============ 8. 错误总结和建议 ============
			# logger.error("💡 ====== ERROR SUMMARY & SUGGESTIONS ======")
			
			# if "screenshot" in str(e).lower():
			# 	logger.error("Issue: Incorrect 'screenshot' action format")
			# 	logger.error("Solution 1: Clean historical messages with wrong format")
			# 	logger.error("Solution 2: Correct system prompt to use: {'evaluate': {'screenshot': true, 'thought': '...'}}")
			# 	logger.error("Solution 3: Add pre-processing to transform {'screenshot': {}} to correct format")
			
			# elif "extra_forbidden" in str(e).lower():
			# 	logger.error("Issue: Unexpected fields in response")
			# 	logger.error("Solution: Check if LLM is returning fields not defined in Pydantic model")
			
			# elif "missing" in str(e).lower():
			# 	logger.error("Issue: Required fields are missing")
			# 	logger.error("Solution: Ensure LLM returns all required fields as per schema")
			
			# logger.error("💥 ====== END ERROR LOG ======")
			# # ============ 添加结束 ============
			raise ModelProviderError(message=str(e), model=self.name) from e