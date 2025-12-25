from functools import cache
from typing import Any, ClassVar

from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from textual.widgets import Static

from .base_renderer import BaseToolRenderer
from .registry import register_tool_renderer


@cache
def _get_style_colors() -> dict[Any, str]:
    style = get_style_by_name("native")
    return {token: f"#{style_def['color']}" for token, style_def in style if style_def["color"]}


@register_tool_renderer
class BrowserUseRenderer(BaseToolRenderer):
    tool_name: ClassVar[str] = "browser_use"
    css_classes: ClassVar[list[str]] = ["tool-call", "browser-tool"]

    @classmethod
    def _get_token_color(cls, token_type: Any) -> str | None:
        colors = _get_style_colors()
        while token_type:
            if token_type in colors:
                return colors[token_type]
            token_type = token_type.parent
        return None

    @classmethod
    def _highlight_js(cls, code: str) -> str:
        lexer = get_lexer_by_name("javascript")
        result_parts: list[str] = []

        for token_type, token_value in lexer.get_tokens(code):
            if not token_value:
                continue

            escaped_value = cls.escape_markup(token_value)
            color = cls._get_token_color(token_type)

            if color:
                result_parts.append(f"[{color}]{escaped_value}[/]")
            else:
                result_parts.append(escaped_value)

        return "".join(result_parts)

    @classmethod
    def render(cls, tool_data: dict[str, Any]) -> Static:
        args = tool_data.get("args", {})
        status = tool_data.get("status", "unknown")

        task = args.get("task", "")
        
        browser_icon = "🌐"
        
        if task:
            display_task = cls._format_task(task)
            message = f"starting browser-use automation: {display_task}"
        else:
            message = "starting browser-use automation"
            
        content = f"{browser_icon} [#06b6d4]{message}[/]"
        css_classes = cls.get_css_classes(status)
        return Static(content, classes=css_classes)

    @classmethod
    def _format_task(cls, task: str) -> str:
        """格式化任务描述"""
        if len(task) > 100:
            task = task[:97] + "..."
        return cls.escape_markup(task)


