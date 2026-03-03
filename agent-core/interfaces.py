from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class VisionAnalysis(BaseModel):
    description: str
    elements: List[Dict[str, Any]]

class UIAction(BaseModel):
    action_type: str
    target: str
    value: Optional[str] = None

class ActionPlan(BaseModel):
    steps: List[UIAction]
    reasoning: str

class ExecutionResult(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class AgentBackend(ABC):
    @abstractmethod
    async def analyze_vision(self, screenshot: str) -> VisionAnalysis:
        pass

    @abstractmethod
    async def plan_workflow(self, goal: str, context: VisionAnalysis) -> ActionPlan:
        pass

    @abstractmethod
    async def execute_ui_action(self, action: UIAction) -> ExecutionResult:
        pass

    @abstractmethod
    async def generate_voice(self, text: str) -> str:
        """Returns URL to TTS audio or base64 audio"""
        pass

    @abstractmethod
    async def interrupt_handler(self) -> None:
        pass
