"""
Pacote comum para agentes Skuld.
"""

from .agent_base import (
    SkuldAgent,
    SkuldMessage,
    SkuldResponse,
    MessagePriority,
    AgentStatus
)

__version__ = "1.0.0"
__all__ = [
    "SkuldAgent",
    "SkuldMessage", 
    "SkuldResponse",
    "MessagePriority",
    "AgentStatus"
]
