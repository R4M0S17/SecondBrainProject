from dataclasses import dataclass
from enum import Enum


class TaskComplexity(str, Enum):
    """Task complexity levels for model selection."""

    TRIVIAL = "trivial"  # short factual answer
    LIGHT = "light"  # chat, brief summary
    MEDIUM = "medium"  # RAG, simple code
    HEAVY = "heavy"  # multi-step reasoning, long analysis
    MAXIMUM = "maximum"  # extensive writing, complex code, research


@dataclass
class TaskProfile:
    """Profile of an incoming task for model selection."""

    complexity: TaskComplexity
    requires_code: bool
    context_length_estimate: int
    required_capabilities: list[str]


def classify(prompt: str, context_tokens: int = 0) -> TaskProfile:
    """Classify task complexity based on prompt heuristics.

    Args:
        prompt: The user's input prompt
        context_tokens: Estimated tokens from RAG/memory context

    Returns:
        TaskProfile with estimated complexity and requirements
    """
    # Estimate prompt tokens (rough: 1 token ≈ 4 chars)
    prompt_tokens = len(prompt) // 4 + 1
    total_tokens = prompt_tokens + context_tokens

    # Detect code requirement
    requires_code = any(
        pattern in prompt.lower()
        for pattern in [
            "```",
            "def ",
            "class ",
            "function ",
            "import ",
            "code",
            "script",
            "program",
            "algorithm",
            "debug",
        ]
    )

    # Keyword-based complexity detection
    heavy_keywords = [
        "analyze",
        "research",
        "investigate",
        "comprehensive",
        "deep",
        "thorough",
        "explain",
        "detailed",
        "breakdown",
        "essay",
        "report",
        "summary",
    ]
    light_keywords = [
        "what is",
        "define",
        "when",
        "where",
        "who",
        "short",
        "brief",
        "quick",
        "tell me",
    ]

    prompt_lower = prompt.lower()
    heavy_count = sum(1 for kw in heavy_keywords if kw in prompt_lower)
    light_count = sum(1 for kw in light_keywords if kw in prompt_lower)

    # Length-based hints
    if total_tokens < 100:
        base_complexity = TaskComplexity.TRIVIAL
    elif total_tokens < 500:
        base_complexity = TaskComplexity.LIGHT
    elif total_tokens < 2000:
        base_complexity = TaskComplexity.MEDIUM
    elif total_tokens < 5000:
        base_complexity = TaskComplexity.HEAVY
    else:
        base_complexity = TaskComplexity.MAXIMUM

    # Adjust based on keyword matches
    if heavy_count > 0:
        if base_complexity == TaskComplexity.TRIVIAL:
            complexity = TaskComplexity.LIGHT
        elif base_complexity == TaskComplexity.LIGHT:
            complexity = TaskComplexity.MEDIUM
        elif base_complexity == TaskComplexity.MEDIUM:
            complexity = TaskComplexity.HEAVY
        else:
            complexity = base_complexity
    elif light_count > 0:
        if base_complexity == TaskComplexity.MAXIMUM:
            complexity = TaskComplexity.HEAVY
        elif base_complexity == TaskComplexity.HEAVY:
            complexity = TaskComplexity.MEDIUM
        elif base_complexity in (TaskComplexity.MEDIUM, TaskComplexity.LIGHT):
            complexity = TaskComplexity.LIGHT
        else:
            complexity = base_complexity
    else:
        complexity = base_complexity

    # Build capability list
    capabilities = ["chat"]
    if requires_code:
        capabilities.append("code")
    if heavy_count > 2 or base_complexity in (TaskComplexity.HEAVY, TaskComplexity.MAXIMUM):
        capabilities.append("reasoning")

    return TaskProfile(
        complexity=complexity,
        requires_code=requires_code,
        context_length_estimate=min(total_tokens, 32768),
        required_capabilities=capabilities,
    )
