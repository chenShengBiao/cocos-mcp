"""Gameplay-code scaffolds: canonical .ts starter scripts.

The rest of cocos-mcp builds scenes and imports assets; it does nothing
to help with the *behavioural* layer (the .ts files that actually run
every frame). Scaffolds close that gap by generating small, well-shaped
runtime modules the orchestrating LLM can attach and wire up — so the
AI doesn't have to reinvent an input singleton or a score tracker from
scratch for every new project.
"""
from .input import scaffold_input_abstraction
from .score import scaffold_score_system

__all__ = ["scaffold_input_abstraction", "scaffold_score_system"]
