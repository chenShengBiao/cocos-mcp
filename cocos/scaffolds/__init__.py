"""Gameplay-code scaffolds: canonical .ts starter scripts.

The rest of cocos-mcp builds scenes and imports assets; it does nothing
to help with the *behavioural* layer (the .ts files that actually run
every frame). Scaffolds close that gap by generating small, well-shaped
runtime modules the orchestrating LLM can attach and wire up — so the
AI doesn't have to reinvent an input singleton, score tracker, player
controller, enemy AI, spawner, or game-loop state machine from scratch
for every new project.
"""
from .audio import scaffold_audio_controller
from .camera_follow import scaffold_camera_follow
from .enemy import scaffold_enemy_ai
from .game_loop import scaffold_game_loop
from .input import scaffold_input_abstraction
from .player import scaffold_player_controller
from .score import scaffold_score_system
from .spawner import scaffold_spawner
from .ui_screen import scaffold_ui_screen

__all__ = [
    "scaffold_audio_controller",
    "scaffold_camera_follow",
    "scaffold_enemy_ai",
    "scaffold_game_loop",
    "scaffold_input_abstraction",
    "scaffold_player_controller",
    "scaffold_score_system",
    "scaffold_spawner",
    "scaffold_ui_screen",
]
