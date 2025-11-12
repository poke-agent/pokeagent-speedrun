"""
Model-Specific Prompt Optimizer

Phase 3.3 implementation from TRACK2_SIMPLE_AGENT_OPTIMIZATION_PLAN.md

Optimizes prompts based on the specific VLM model being used.
Different models have different strengths, context limits, and formatting preferences.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ModelOptimizer:
    """
    Optimizes prompts and parameters based on model characteristics.

    Models have different capabilities:
    - Gemini Flash/Pro: Fast, handles long context, good with structured prompts
    - GPT-4o/GPT-4-turbo: Excellent reasoning, longer context, strategic thinking
    - o3-mini: Fast reasoning, structured prompts, concise responses
    - Local models (Qwen2-VL, Phi-3.5): Limited context, need compact prompts
    """

    # Model configuration database
    MODEL_CONFIGS = {
        # Gemini models
        "gemini-2.5-flash": {
            "family": "gemini",
            "context_window": 1000000,  # 1M tokens
            "strengths": ["speed", "long_context", "vision"],
            "prompt_style": "detailed",
            "max_prompt_tokens": 8000,
            "compact_mode": False,
            "add_strategic_context": True,
            "add_examples": True,
        },
        "gemini-2.5-pro": {
            "family": "gemini",
            "context_window": 2000000,  # 2M tokens
            "strengths": ["reasoning", "long_context", "vision"],
            "prompt_style": "detailed",
            "max_prompt_tokens": 10000,
            "compact_mode": False,
            "add_strategic_context": True,
            "add_examples": True,
        },

        # OpenAI models
        "gpt-4o": {
            "family": "gpt4",
            "context_window": 128000,
            "strengths": ["reasoning", "strategic_thinking", "complex_tasks"],
            "prompt_style": "detailed_strategic",
            "max_prompt_tokens": 8000,
            "compact_mode": False,
            "add_strategic_context": True,
            "add_examples": True,
        },
        "gpt-4-turbo": {
            "family": "gpt4",
            "context_window": 128000,
            "strengths": ["reasoning", "vision", "complex_tasks"],
            "prompt_style": "detailed_strategic",
            "max_prompt_tokens": 8000,
            "compact_mode": False,
            "add_strategic_context": True,
            "add_examples": True,
        },
        "o3-mini": {
            "family": "o3",
            "context_window": 200000,
            "strengths": ["fast_reasoning", "structured_thinking", "efficiency"],
            "prompt_style": "structured",
            "max_prompt_tokens": 6000,
            "compact_mode": False,
            "add_strategic_context": True,
            "add_examples": False,  # Prefers reasoning over examples
        },

        # Local models
        "qwen2-vl": {
            "family": "local",
            "context_window": 32000,
            "strengths": ["speed", "vision"],
            "prompt_style": "compact",
            "max_prompt_tokens": 3000,
            "compact_mode": True,
            "add_strategic_context": False,
            "add_examples": False,
        },
        "phi-3.5-vision": {
            "family": "local",
            "context_window": 128000,
            "strengths": ["vision", "reasoning"],
            "prompt_style": "moderate",
            "max_prompt_tokens": 4000,
            "compact_mode": False,
            "add_strategic_context": True,
            "add_examples": False,
        },
        "qwen3-vl-4b-instruct": {
            "family": "local",
            "context_window": 6000,
            "strengths": ["speed", "vision"],
            "prompt_style": "compact",
            "max_prompt_tokens": 5000,
            "compact_mode": True,
            "add_strategic_context": False,
            "add_examples": False,
        },
         "qwen3-vl-4b-instruct-mlx": {
            "family": "local",
            "context_window": 6000,
            "strengths": ["speed", "vision"],
            "prompt_style": "compact",
            "max_prompt_tokens": 5000,
            "compact_mode": False,
            "add_strategic_context": True,
            "add_examples": False,
        },

        # Defaults
        "default": {
            "family": "unknown",
            "context_window": 8000,
            "strengths": ["general"],
            "prompt_style": "moderate",
            "max_prompt_tokens": 4000,
            "compact_mode": False,
            "add_strategic_context": True,
            "add_examples": True,
        },
    }

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        """
        Initialize optimizer for specific model.

        Args:
            model_name: Name of the VLM model (e.g., "gemini-2.5-flash", "gpt-4o")
        """
        self.model_name = model_name.lower()
        self.config = self._get_model_config()

        logger.info(
            f"Model Optimizer initialized for {model_name} "
            f"(family: {self.config['family']}, style: {self.config['prompt_style']})"
        )

    def _get_model_config(self) -> Dict[str, Any]:
        """Get configuration for the current model"""
        # Try exact match
        if self.model_name in self.MODEL_CONFIGS:
            return self.MODEL_CONFIGS[self.model_name]

        # Try partial match
        for key, config in self.MODEL_CONFIGS.items():
            if key in self.model_name or self.model_name in key:
                logger.info(f"Matched model '{self.model_name}' to config '{key}'")
                return config

        # Try family detection
        if "gemini" in self.model_name:
            logger.info(f"Detected Gemini family for '{self.model_name}', using gemini-2.5-flash config")
            return self.MODEL_CONFIGS["gemini-2.5-flash"]
        elif "gpt-4" in self.model_name:
            logger.info(f"Detected GPT-4 family for '{self.model_name}', using gpt-4o config")
            return self.MODEL_CONFIGS["gpt-4o"]
        elif "o3" in self.model_name or "o1" in self.model_name:
            logger.info(f"Detected OpenAI reasoning model for '{self.model_name}', using o3-mini config")
            return self.MODEL_CONFIGS["o3-mini"]
        elif "qwen" in self.model_name:
            logger.info(f"Detected Qwen model for '{self.model_name}', using qwen2-vl config")
            return self.MODEL_CONFIGS["qwen2-vl"]
        elif "phi" in self.model_name:
            logger.info(f"Detected Phi model for '{self.model_name}', using phi-3.5-vision config")
            return self.MODEL_CONFIGS["phi-3.5-vision"]

        # Default
        logger.warning(f"Unknown model '{self.model_name}', using default config")
        return self.MODEL_CONFIGS["default"]

    def should_use_compact_prompt(self) -> bool:
        """Check if compact prompt mode should be used"""
        return self.config["compact_mode"]

    def get_max_prompt_tokens(self) -> int:
        """Get recommended maximum prompt tokens for this model"""
        return self.config["max_prompt_tokens"]

    def get_history_detail_count(self) -> int:
        """Get recommended number of history entries to show in full detail"""
        # Adjust based on context window
        if self.config["context_window"] >= 128000:
            return 30  # Large context: more history
        elif self.config["context_window"] >= 32000:
            return 20  # Medium context: moderate history
        else:
            return 10  # Small context: less history

    def get_actions_display_count(self) -> int:
        """Get recommended number of recent actions to display"""
        # Adjust based on context window
        if self.config["context_window"] >= 128000:
            return 50  # Large context
        elif self.config["context_window"] >= 32000:
            return 30  # Medium context
        else:
            return 20  # Small context

    def should_add_strategic_context(self) -> bool:
        """Check if strategic context should be included"""
        return self.config["add_strategic_context"]

    def should_add_examples(self) -> bool:
        """Check if few-shot examples should be included"""
        return self.config["add_examples"]

    def optimize_prompt(self, base_prompt: str, context: str = "overworld") -> str:
        """
        Optimize prompt for the specific model.

        Args:
            base_prompt: Original prompt text
            context: Game context (battle, dialogue, overworld)

        Returns:
            Optimized prompt for the model
        """
        # For compact mode, prompt is already optimized via get_compact_prompt
        if self.should_use_compact_prompt():
            return base_prompt

        # Add model-specific enhancements
        optimized = base_prompt

        # GPT-4 models: Add strategic planning emphasis
        if self.config["family"] == "gpt4":
            if context == "overworld":
                strategic_emphasis = """
🧠 STRATEGIC THINKING (GPT-4 Optimization):
Before choosing your action, consider:
1. What is the optimal path to the next milestone?
2. What are potential obstacles or inefficiencies?
3. How can I minimize total actions while staying on the critical path?

Think step-by-step about long-term efficiency, not just immediate progress.
"""
                optimized = strategic_emphasis + "\n" + optimized

        # o3-mini: Add structured reasoning prompt
        elif self.config["family"] == "o3":
            reasoning_structure = """
📋 REASONING STRUCTURE:
1. **Assess**: What is the current situation and objective?
2. **Plan**: What are the 2-3 best options and their expected outcomes?
3. **Decide**: Which option maximizes progress with minimum actions?
4. **Execute**: Output your chosen action with brief reasoning.

Be concise and systematic in your decision-making process.
"""
            optimized = reasoning_structure + "\n" + optimized

        # Gemini models: Emphasize vision and context
        elif self.config["family"] == "gemini":
            if context == "battle":
                vision_emphasis = """
👁️ VISUAL ANALYSIS (Gemini Optimization):
- Examine the battle screen carefully for HP bars, move names, and Pokemon sprites
- Use visual cues to confirm battle state (your turn, opponent's turn, victory/defeat)
- Cross-reference visual information with game state data for accuracy

Gemini excels at vision - use the visual frame as primary source of truth.
"""
                optimized = vision_emphasis + "\n" + optimized

        return optimized

    def get_recommended_settings(self) -> Dict[str, Any]:
        """
        Get recommended settings for the agent based on model.

        Returns:
            Dictionary of recommended settings
        """
        return {
            "use_compact_prompt": self.should_use_compact_prompt(),
            "max_prompt_tokens": self.get_max_prompt_tokens(),
            "history_detail_count": self.get_history_detail_count(),
            "actions_display_count": self.get_actions_display_count(),
            "add_strategic_context": self.should_add_strategic_context(),
            "add_examples": self.should_add_examples(),
            "model_family": self.config["family"],
            "prompt_style": self.config["prompt_style"],
        }

    def format_settings_for_display(self) -> str:
        """Format recommended settings as human-readable string"""
        settings = self.get_recommended_settings()

        lines = [
            "=" * 60,
            f"MODEL OPTIMIZER SETTINGS - {self.model_name}",
            "=" * 60,
            f"Model Family: {settings['model_family']}",
            f"Prompt Style: {settings['prompt_style']}",
            f"",
            f"Prompt Settings:",
            f"  • Use Compact Mode: {settings['use_compact_prompt']}",
            f"  • Max Prompt Tokens: {settings['max_prompt_tokens']}",
            f"  • History Detail Count: {settings['history_detail_count']}",
            f"  • Actions Display Count: {settings['actions_display_count']}",
            f"",
            f"Content Settings:",
            f"  • Add Strategic Context: {settings['add_strategic_context']}",
            f"  • Add Few-Shot Examples: {settings['add_examples']}",
            "=" * 60,
        ]

        return "\n".join(lines)


# Convenience function
def get_optimizer_for_model(model_name: str) -> ModelOptimizer:
    """
    Get a model optimizer for the specified model.

    Args:
        model_name: Name of the VLM model

    Returns:
        ModelOptimizer instance configured for the model
    """
    return ModelOptimizer(model_name)


# Auto-detect from environment
def get_optimizer_from_env() -> Optional[ModelOptimizer]:
    """
    Try to detect model from environment and create optimizer.

    Returns:
        ModelOptimizer if model detected, None otherwise
    """
    import os

    # Try to detect from common environment variables
    model_name = None

    if os.getenv("GEMINI_API_KEY"):
        model_name = "gemini-2.5-flash"
    elif os.getenv("OPENAI_API_KEY"):
        model_name = "gpt-4o"

    if model_name:
        logger.info(f"Auto-detected model from environment: {model_name}")
        return ModelOptimizer(model_name)

    return None
