"""Local-LLM agent: client, tool registry, and the loop that ties them together."""

from parallax.ai.agent import Agent, AgentResult, AgentStep
from parallax.ai.llm import AssistantMessage, LLMClient, LLMError
from parallax.ai.tools import Tool, ToolContext, ToolRegistry

__all__ = [
    "Agent",
    "AgentResult",
    "AgentStep",
    "AssistantMessage",
    "LLMClient",
    "LLMError",
    "Tool",
    "ToolContext",
    "ToolRegistry",
]
