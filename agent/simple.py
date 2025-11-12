"""
Simple Agent Module

Provides a streamlined approach for direct frame + state -> action processing,
with enhanced history tracking to prevent getting stuck in loops.

Key improvements over the original simple mode:
- Location-based stuck detection (tracks repeated actions at same coordinates)
- Context-aware history (overworld/battle/menu/dialogue awareness)
- Memory management to fit within LLM context limits
- Detailed history tracking with timestamps and game state summaries
- Smart context switching that helps agent avoid infinite loops
- Configurable history window sizes for different use cases
- Chain of thought reasoning with structured LLM responses
- Objectives system with automatic and manual completion tracking
- Dynamic goal setting and progress monitoring

The agent maintains objectives (go to location, battle trainer, etc.) that are
automatically tracked and marked complete when achieved. The LLM can also
manually complete objectives and create new ones dynamically through structured
commands. It uses chain of thought reasoning to make better decisions while
considering current objectives. All state including objectives is forwarded
to support external monitoring and debugging.

Configuration defaults (can be customized):
- 100 previous state/location entries (with context and reasoning)
- 50 recent button presses tracked
- 15 history entries shown to LLM in prompts
- 20 recent actions shown to LLM in prompts
- Automatic memory management to stay within LLM context limits
"""

import logging
import os
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from utils.agent_helpers import update_server_metrics
from utils.pathfinding import Pathfinder
from utils.state_formatter import format_state_for_llm
from utils.battle_analyzer import BattleAnalyzer
from utils.strategic_memory import StrategicMemory
from utils.speedrun_router import SpeedrunRouter
from utils.history_compressor import HistoryCompressor
from utils.performance_metrics import PerformanceMetrics
from utils.model_optimizer import ModelOptimizer
from utils.collision_handler import get_collision_handler
from agent.prompt_templates import get_compact_prompt, get_full_prompt

logger = logging.getLogger(__name__)

# Configurable parameters for history tracking
DEFAULT_MAX_HISTORY_ENTRIES = 100  # Previous states/locations with context
DEFAULT_MAX_RECENT_ACTIONS = 50  # Recent button presses
DEFAULT_HISTORY_DISPLAY_COUNT = 30  # Number of history entries shown to LLM
DEFAULT_ACTIONS_DISPLAY_COUNT = 40  # Number of recent actions shown to LLM
DEFAULT_MOVEMENT_MEMORY_CLEAR_INTERVAL = 30  # Clear movement memory after N actions (0 = never clear)


def configure_simple_agent_defaults(
    max_history_entries: int = None,
    max_recent_actions: int = None,
    history_display_count: int = None,
    actions_display_count: int = None,
    movement_memory_clear_interval: int = None,
):
    """Configure default parameters for all new SimpleAgent instances"""
    global DEFAULT_MAX_HISTORY_ENTRIES, DEFAULT_MAX_RECENT_ACTIONS
    global DEFAULT_HISTORY_DISPLAY_COUNT, DEFAULT_ACTIONS_DISPLAY_COUNT
    global DEFAULT_MOVEMENT_MEMORY_CLEAR_INTERVAL

    if max_history_entries is not None:
        DEFAULT_MAX_HISTORY_ENTRIES = max_history_entries
    if max_recent_actions is not None:
        DEFAULT_MAX_RECENT_ACTIONS = max_recent_actions
    if history_display_count is not None:
        DEFAULT_HISTORY_DISPLAY_COUNT = history_display_count
    if actions_display_count is not None:
        DEFAULT_ACTIONS_DISPLAY_COUNT = actions_display_count
    if movement_memory_clear_interval is not None:
        DEFAULT_MOVEMENT_MEMORY_CLEAR_INTERVAL = movement_memory_clear_interval

    logger.info(
        f"Updated SimpleAgent defaults: {DEFAULT_MAX_HISTORY_ENTRIES} history, {DEFAULT_MAX_RECENT_ACTIONS} actions, "
        f"display {DEFAULT_HISTORY_DISPLAY_COUNT}/{DEFAULT_ACTIONS_DISPLAY_COUNT}, "
        f"movement memory clear interval: {DEFAULT_MOVEMENT_MEMORY_CLEAR_INTERVAL}"
    )


@dataclass
class Objective:
    """Single objective/goal for the agent"""

    id: str
    description: str
    objective_type: str  # "location", "battle", "item", "dialogue", "custom"
    target_value: Optional[Any] = None  # Specific target (coords, trainer name, item name, etc.)
    target_coords: Optional[Tuple[int, int]] = None  # Target coordinates for auto-navigation
    target_floor: Optional[int] = None  # Target floor number for multi-floor navigation
    target_object: Optional[str] = None  # Target map symbol (S=stairs, D=door, N=NPC, etc.)
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    progress_notes: str = ""
    storyline: bool = False  # True for main storyline objectives (auto-verified), False for agent sub-objectives
    milestone_id: Optional[str] = None  # Emulator milestone ID for storyline objectives


@dataclass
class HistoryEntry:
    """Single entry in the agent's history"""

    timestamp: datetime
    player_coords: Optional[Tuple[int, int]]
    map_id: Optional[int]
    context: str  # "overworld", "battle", "menu", "dialogue"
    action_taken: str
    game_state_summary: str


@dataclass
class SimpleAgentState:
    """Maintains history and state for the simple agent"""

    # Note: We don't use defaults here because they're captured at class definition time
    history: deque = None
    recent_actions: deque = None
    stuck_detection: Dict[str, int] = field(default_factory=dict)
    step_counter: int = 0
    objectives: List[Objective] = field(default_factory=list)
    objectives_updated: bool = False
    failed_movements: Dict[str, List[str]] = field(default_factory=dict)  # coord_key -> [failed_directions]
    npc_interactions: Dict[str, str] = field(default_factory=dict)  # coord_key -> interaction_notes
    movement_memory_action_counter: int = 0  # Counter for tracking actions since last memory clear

    def __post_init__(self):
        """Initialize deques with current default values"""
        if self.history is None:
            self.history = deque(maxlen=DEFAULT_MAX_HISTORY_ENTRIES)
        if self.recent_actions is None:
            self.recent_actions = deque(maxlen=DEFAULT_MAX_RECENT_ACTIONS)


class SimpleAgent:
    """
    Simple agent that processes frame + state -> action directly with history tracking
    """

    def __init__(
        self,
        vlm,
        max_history_entries: int = None,
        max_recent_actions: int = None,
        history_display_count: int = None,
        actions_display_count: int = None,
        movement_memory_clear_interval: int = None,
    ):
        self.vlm = vlm

        # Use current global defaults if not specified
        max_history_entries = max_history_entries or DEFAULT_MAX_HISTORY_ENTRIES
        max_recent_actions = max_recent_actions or DEFAULT_MAX_RECENT_ACTIONS
        history_display_count = history_display_count or DEFAULT_HISTORY_DISPLAY_COUNT
        actions_display_count = actions_display_count or DEFAULT_ACTIONS_DISPLAY_COUNT
        movement_memory_clear_interval = (
            movement_memory_clear_interval
            if movement_memory_clear_interval is not None
            else DEFAULT_MOVEMENT_MEMORY_CLEAR_INTERVAL
        )

        self.state = SimpleAgentState()
        self.state.history = deque(maxlen=max_history_entries)
        self.state.recent_actions = deque(maxlen=max_recent_actions)

        # Display parameters for LLM prompts
        self.history_display_count = history_display_count
        self.actions_display_count = actions_display_count

        # Movement memory clearing interval
        self.movement_memory_clear_interval = movement_memory_clear_interval

        # Initialize pathfinder for automatic navigation
        self.pathfinder = Pathfinder(allow_diagonal=False)
        self.navigation_path = None  # Current navigation path being executed
        self.navigation_target = None  # Target coordinates (x, y) for navigation
        self.navigation_stuck_count = 0  # Track if navigation is stuck

        # Map change detection for clearing navigation on warps
        self.last_map_id = None  # Track previous map ID to detect warps/floor changes

        # Frontier-based exploration state
        self.unreachable_frontiers = set()  # Track frontiers that cannot be reached
        self.last_detected_frontiers = []  # Cache last detected frontiers for frontier navigation
        self.consecutive_collisions = 0  # Track collisions for frontier abandonment
        self.consecutive_movements = 0  # Track successful movements

        # Frame similarity detection (Phase 1.1 optimization)
        self.last_frame = None
        self.last_frame_hash = None
        self.frame_skip_count = 0  # Track how many frames we've skipped
        self.last_vlm_action = None  # Remember last action when skipping frames

        # Battle analyzer (Phase 1.3 optimization)
        self.battle_analyzer = BattleAnalyzer()

        # Strategic memory system (Phase 2.1 optimization)
        self.strategic_memory = StrategicMemory()

        # Speedrun router (Phase 2.2 optimization)
        self.speedrun_router = SpeedrunRouter()

        # History compressor (Phase 3.1 optimization)
        self.history_compressor = HistoryCompressor(
            full_detail_count=history_display_count,
            summary_batch_size=10
        )

        # Performance metrics (Phase 3.2 optimization)
        self.performance_metrics = PerformanceMetrics()

        # Model optimizer (Phase 3.3 optimization)
        # Detect model name from VLM backend and optimize prompts accordingly
        model_name = getattr(vlm, 'model_name', 'gemini-2.5-flash')  # Default to Gemini Flash
        self.model_optimizer = ModelOptimizer(model_name)
        logger.info(f"Model optimizer settings:\n{self.model_optimizer.format_settings_for_display()}")

        # Collision handler (Phase 5.1 optimization)
        # Intelligent collision tracking and recovery
        self.collision_handler = get_collision_handler()
        logger.info("Collision handler initialized (5 collision limit, 2 movement reset)")

        # Track last battle state for recording outcomes
        self.last_battle_state = None
        self.current_battle_turn = 0

        # Initialize storyline objectives for Emerald progression
        self._initialize_storyline_objectives()

    def _initialize_storyline_objectives(self):
        """Initialize the main storyline objectives for Pokémon Emerald progression"""
        storyline_objectives = [
            {
                "id": "story_game_start",
                "description": "Complete title sequence and begin the game",
                "objective_type": "system",
                "target_value": "Game Running",
                "milestone_id": "GAME_RUNNING",
            },
            {
                "id": "story_intro_complete",
                "description": "Complete intro cutscene with moving van",
                "objective_type": "cutscene",
                "target_value": "Intro Complete",
                "target_object": "S",
                "milestone_id": "INTRO_CUTSCENE_COMPLETE",
            },
            {
                "id": "story_player_house",
                "description": "Enter player's house for the first time",
                "objective_type": "location",
                "target_value": "Player's House",
                "milestone_id": "PLAYER_HOUSE_ENTERED",
            },
            {
                "id": "story_player_bedroom",
                "description": "Go upstairs to player's bedroom",
                "objective_type": "location",
                "target_value": "Player's Bedroom",
                "milestone_id": "PLAYER_BEDROOM",
            },
            {
                "id": "story_clock_set",
                "description": "Set the clock on the wall in the player's bedroom. Interact with the clock at (5,1) by pressing A while facing it. Then, leave the house.",
                "objective_type": "location",
                "target_value": "Clock Set",
                "target_floor": 2,
                "target_coords": (5, 1),  # Clock position on 2nd floor
                "milestone_id": "CLOCK_SET",
            },
            {
                "id": "story_rival_house",
                "description": "Visit May's house next door",
                "objective_type": "location",
                "target_value": "Rival's House",
                "milestone_id": "RIVAL_HOUSE",
            },
            {
                "id": "story_rival_bedroom",
                "description": "Visit May's bedroom on the second floor",
                "objective_type": "location",
                "target_value": "Rival's Bedroom",
                "milestone_id": "RIVAL_BEDROOM",
            },
            {
                "id": "story_route_101",
                "description": "Travel north to Route 101 and encounter Prof. Birch",
                "objective_type": "location",
                "target_value": "Route 101",
                "milestone_id": "ROUTE_101",
            },
            {
                "id": "story_starter_chosen",
                "description": "Choose starter Pokémon and receive first party member",
                "objective_type": "pokemon",
                "target_value": "Starter Pokémon",
                "milestone_id": "STARTER_CHOSEN",
            },
            {
                "id": "story_birch_lab",
                "description": "Visit Professor Birch's lab in Littleroot Town and receive the Pokedex",
                "objective_type": "location",
                "target_value": "Birch's Lab",
                "milestone_id": "BIRCH_LAB_VISITED",
            },
            {
                "id": "story_oldale_town",
                "description": "Leave lab and continue journey north to Oldale Town",
                "objective_type": "location",
                "target_value": "Oldale Town",
                "milestone_id": "OLDALE_TOWN",
            },
            {
                "id": "story_route_103",
                "description": "Travel to Route 103 to meet rival",
                "objective_type": "location",
                "target_value": "Route 103",
                "milestone_id": "ROUTE_103",
            },
            {
                "id": "story_received_pokedex",
                "description": "Return to Birch's lab and receive the Pokédex",
                "objective_type": "item",
                "target_value": "Pokédex",
                "milestone_id": "RECEIVED_POKEDEX",
            },
            {
                "id": "story_route_102",
                "description": "Return through Route 102 toward Petalburg City",
                "objective_type": "location",
                "target_value": "Route 102",
                "milestone_id": "ROUTE_102",
            },
            {
                "id": "story_petalburg_city",
                "description": "Navigate to Petalburg City and visit Dad's gym",
                "objective_type": "location",
                "target_value": "Petalburg City",
                "milestone_id": "PETALBURG_CITY",
            },
            {
                "id": "story_dad_meeting",
                "description": "Meet Dad at Petalburg City Gym",
                "objective_type": "dialogue",
                "target_value": "Dad Meeting",
                "milestone_id": "DAD_FIRST_MEETING",
            },
            {
                "id": "story_gym_explanation",
                "description": "Receive explanation about Gym challenges",
                "objective_type": "dialogue",
                "target_value": "Gym Tutorial",
                "milestone_id": "GYM_EXPLANATION",
            },
            {
                "id": "story_route_104_south",
                "description": "Travel through southern section of Route 104",
                "objective_type": "location",
                "target_value": "Route 104 South",
                "milestone_id": "ROUTE_104_SOUTH",
            },
            {
                "id": "story_petalburg_woods",
                "description": "Navigate through Petalburg Woods to help Devon researcher",
                "objective_type": "location",
                "target_value": "Petalburg Woods",
                "milestone_id": "PETALBURG_WOODS",
            },
            {
                "id": "story_aqua_grunt",
                "description": "Defeat Team Aqua Grunt in Petalburg Woods",
                "objective_type": "battle",
                "target_value": "Aqua Grunt Defeated",
                "milestone_id": "TEAM_AQUA_GRUNT_DEFEATED",
            },
            {
                "id": "story_route_104_north",
                "description": "Travel through northern section of Route 104 to Rustboro",
                "objective_type": "location",
                "target_value": "Route 104 North",
                "milestone_id": "ROUTE_104_NORTH",
            },
            {
                "id": "story_rustboro_city",
                "description": "Arrive in Rustboro City and deliver Devon Goods",
                "objective_type": "location",
                "target_value": "Rustboro City",
                "milestone_id": "RUSTBORO_CITY",
            },
            {
                "id": "story_rustboro_gym",
                "description": "Enter the Rustboro Gym and challenge Roxanne",
                "objective_type": "location",
                "target_value": "Rustboro Gym",
                "milestone_id": "RUSTBORO_GYM_ENTERED",
            },
            {
                "id": "story_roxanne_defeated",
                "description": "Defeat Gym Leader Roxanne",
                "objective_type": "battle",
                "target_value": "Roxanne Defeated",
                "milestone_id": "ROXANNE_DEFEATED",
            },
            {
                "id": "story_stone_badge",
                "description": "Receive the Stone Badge and complete first gym",
                "objective_type": "badge",
                "target_value": "Stone Badge",
                "milestone_id": "FIRST_GYM_COMPLETE",
            },
        ]

        # Add storyline objectives to the state
        for obj_data in storyline_objectives:
            objective = Objective(
                id=obj_data["id"],
                description=obj_data["description"],
                objective_type=obj_data["objective_type"],
                target_value=obj_data["target_value"],
                target_coords=obj_data.get("target_coords"),  # Optional navigation coordinates
                target_floor=obj_data.get("target_floor"),  # Optional floor number
                target_object=obj_data.get("target_object"),  # Optional map symbol to find
                completed=False,
                progress_notes="Storyline objective - verified by emulator milestones",
                storyline=True,
                milestone_id=obj_data["milestone_id"],
            )
            self.state.objectives.append(objective)

        logger.info(
            f"Initialized {len(storyline_objectives)} storyline objectives for Emerald progression (up to first gym)"
        )

    def get_game_context(self, game_state: Dict[str, Any]) -> str:
        """Determine current game context (overworld, battle, menu, dialogue)"""
        try:
            # Check if in title sequence first
            player_location = game_state.get("player", {}).get("location", "")
            if player_location == "TITLE_SEQUENCE":
                return "title"

            # Check game state for title/intro
            game_state_value = game_state.get("game", {}).get("game_state", "").lower()
            if "title" in game_state_value or "intro" in game_state_value:
                return "title"

            # Check if player has party Pokemon - if yes, definitely NOT on title screen
            game_section = game_state.get("game", {})
            party_raw = game_section.get("party")

            # Debug: Log what we're seeing
            logger.info(f"🔍 DEBUG: game_section type: {type(game_section)}")
            logger.info(f"🔍 DEBUG: party_raw type: {type(party_raw)}, value: {party_raw}")

            party = party_raw or []
            has_pokemon = len(party) > 0

            # Check if player name is not set (indicates title sequence)
            # BUT: if we have Pokemon in party, we're definitely in-game even if name is corrupted
            player_name = game_state.get("player", {}).get("name", "").strip()

            # Debug logging
            if has_pokemon:
                logger.info(f"✅ Context detection: Has Pokemon in party ({len(party)}), NOT title screen")
            else:
                logger.info(f"⚠️  Context detection: party is empty/None, has_pokemon={has_pokemon}")

            if (not player_name or player_name == "????????") and not has_pokemon:
                logger.info(
                    f"⚠️  Context detection: No valid player name ('{player_name}') and no Pokemon → title screen"
                )
                return "title"

            # Check if in battle
            is_in_battle = game_state.get("game", {}).get("is_in_battle", False)
            if is_in_battle:
                logger.debug(f"Detected battle context")
                return "battle"

            # Check if dialogue is active using memory reader's reliable detection
            dialogue_detected = game_state.get("game", {}).get("dialogue_detected", {})
            has_dialogue = dialogue_detected.get("has_dialogue", False)

            # IMPORTANT: Cross-check with game_state to avoid false positives from residual text
            # If game_state is "overworld", don't trust dialogue detection alone
            game_state_value = game_state.get("game", {}).get("game_state", "").lower()
            if has_dialogue and game_state_value == "overworld":
                # Dialogue detected but game_state says overworld - likely residual text
                logger.debug(f"Dialogue detected but game_state is 'overworld' - treating as residual text")
                has_dialogue = False

            # Fallback to old method if dialogue_detected not available
            if not has_dialogue:
                dialogue_state = game_state.get("game", {}).get("dialogue", {})
                has_dialogue = dialogue_state.get("active", False) or bool(dialogue_state.get("text", "").strip())

            if has_dialogue:
                logger.debug(f"Detected dialogue context (memory reader)")
                return "dialogue"

            # Check if in menu (simplified detection)
            # Could be enhanced with more sophisticated menu detection
            player_state = game_state.get("player", {})
            if player_state.get("in_menu", False):
                return "menu"

            # Default to overworld
            return "overworld"

        except Exception as e:
            logger.warning(f"Error determining game context: {e}")
            return "unknown"

    def get_player_coords(self, game_state: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        """Extract player coordinates from game state"""
        try:
            player = game_state.get("player", {})
            # Try position.x/y first (standard format)
            position = player.get("position", {})
            if position:
                x = position.get("x")
                y = position.get("y")
                if x is not None and y is not None:
                    return (x, y)

            # Fallback: try direct x/y on player
            x = player.get("x")
            y = player.get("y")
            if x is not None and y is not None:
                return (x, y)
        except Exception as e:
            logger.warning(f"Error getting player coords: {e}")
        return None

    def get_map_id(self, game_state: Dict[str, Any]) -> Optional[int]:
        """Extract map ID from game state (constructed from bank and number)"""
        try:
            map_data = game_state.get("map", {})
            # Try direct ID first
            map_id = map_data.get("id")
            if map_id is not None:
                return map_id

            # Construct ID from bank and number (e.g., bank=1, number=0 → id=256)
            bank = map_data.get("bank")
            number = map_data.get("number")
            if bank is not None and number is not None:
                # Pokemon Emerald map encoding: bank * 256 + number
                constructed_id = bank * 256 + number
                return constructed_id

            logger.warning(f"🗺️ CLAUDE DEBUG: map_id is None! map_data keys: {list(map_data.keys())}")
            return None
        except Exception as e:
            logger.warning(f"Error getting map ID: {e}")
        return None

    def start_navigation(self, target: Tuple[int, int], game_state: Dict[str, Any]) -> bool:
        """
        Start automatic navigation to target coordinates using A* pathfinding.

        Args:
            target: Target coordinates (x, y)
            game_state: Current game state with map data

        Returns:
            True if path found and navigation started, False otherwise
        """
        current_pos = self.get_player_coords(game_state)
        logger.warning(f"🧭 CLAUDE DEBUG: start_navigation called: current_pos={current_pos}, target={target}")
        if not current_pos:
            logger.warning("❌ CLAUDE DEBUG: Cannot start navigation: no player coordinates")
            return False

        if current_pos == target:
            logger.warning(f"⚠️ CLAUDE DEBUG: Already at target {target}")
            self.navigation_path = None
            self.navigation_target = None
            return False

        # Calculate path using A* pathfinding
        logger.warning(f"🧭 CLAUDE DEBUG: Calculating path from {current_pos} to {target}...")
        path_buttons = self.pathfinder.find_path(current_pos, target, game_state, max_distance=50)
        logger.warning(f"🔍 CLAUDE DEBUG: Pathfinding returned: {path_buttons}")

        if not path_buttons:
            logger.warning(f"❌ CLAUDE DEBUG: No path found from {current_pos} to {target}")
            self.navigation_path = None
            self.navigation_target = None
            return False

        logger.warning(
            f"✅ CLAUDE DEBUG: Path found: {len(path_buttons)} steps - {path_buttons[:10]}{'...' if len(path_buttons) > 10 else ''}"
        )
        self.navigation_path = path_buttons
        self.navigation_target = target
        self.navigation_stuck_count = 0
        return True

    def get_next_navigation_action(self, game_state: Dict[str, Any]) -> Optional[str]:
        """
        Get next action from current navigation path.

        Returns None if navigation complete or failed.
        """
        if not self.navigation_path or not self.navigation_target:
            return None

        # Check if we reached the target
        current_pos = self.get_player_coords(game_state)
        if current_pos == self.navigation_target:
            logger.info(f"🎯 Reached navigation target {self.navigation_target}")
            self.navigation_path = None
            self.navigation_target = None
            self.navigation_stuck_count = 0
            return None

        # Check if navigation is stuck (same position for multiple steps)
        if len(self.state.recent_actions) >= 5:
            recent_coords = []
            for entry in list(self.state.history)[-5:]:
                if entry.player_coords:
                    recent_coords.append(entry.player_coords)

            # If all recent coords are the same, navigation is stuck
            if len(recent_coords) >= 5 and len(set(recent_coords)) == 1:
                self.navigation_stuck_count += 1
                if self.navigation_stuck_count >= 3:
                    logger.warning(f"🚨 Navigation stuck at {current_pos}, aborting path and falling back to VLM")
                    self.navigation_path = None
                    self.navigation_target = None
                    self.navigation_stuck_count = 0
                    return None

        # Get next action from path
        if self.navigation_path:
            next_action = self.navigation_path.pop(0)
            logger.debug(f"🧭 Navigation: {next_action} (remaining: {len(self.navigation_path)} steps)")
            return next_action

        return None

    def clear_navigation(self):
        """Clear current navigation path"""
        self.navigation_path = None
        self.navigation_target = None
        self.navigation_stuck_count = 0

    def _navigate_to_frontier_index(self, frontier_index: int, game_state: Dict[str, Any]) -> Optional[str]:
        """
        Navigate to a frontier selected by index from last detection.

        Args:
            frontier_index: 1-based index of frontier from VLM prompt (1-5)
            game_state: Current game state

        Returns:
            First navigation action, or None if navigation failed
        """
        try:
            # Convert to 0-based index
            index = frontier_index - 1

            if not self.last_detected_frontiers or index < 0 or index >= len(self.last_detected_frontiers):
                logger.warning(f"Invalid frontier index {frontier_index} (have {len(self.last_detected_frontiers)} frontiers)")
                return None

            # Get frontier coordinates
            score, target_x, target_y = self.last_detected_frontiers[index]
            target = (target_x, target_y)

            logger.info(f"🎯 VLM selected FRONTIER_{frontier_index}: {target} (score: {score:.1f})")

            # Start navigation to frontier
            if self.start_navigation(target, game_state):
                # Get first action from navigation path
                action = self.get_next_navigation_action(game_state)
                if action:
                    logger.info(f"🧭 Starting frontier navigation: {action} toward {target}")
                    return action

            logger.warning(f"Failed to start navigation to frontier {target}")
            return None

        except Exception as e:
            logger.error(f"Error navigating to frontier index {frontier_index}: {e}", exc_info=True)
            return None

    def find_object_on_map(self, game_state: Dict[str, Any], symbol: str) -> Optional[Tuple[int, int]]:
        """
        Find any object by symbol on the current map.

        Args:
            symbol: Map symbol to search for (S=stairs, D=door, N=NPC, etc.)

        Returns coordinates of object if found, None otherwise.
        """
        try:
            # Generate map grid from tile data (ALLOWED - agent code can use existing tile data)
            # This is NOT modifying memory_reader.py which is prohibited
            map_info = game_state.get("map", {})
            tiles = map_info.get("tiles")

            if not tiles:
                logger.warning(f"No tile data available to find object '{symbol}'")
                return None

            # Convert tiles to symbol grid using map_formatter (allowed utility)
            from utils.map_formatter import format_map_grid

            player_data = game_state.get("player", {})
            player_pos = player_data.get("position", {})
            player_coords = (player_pos.get("x", 0), player_pos.get("y", 0)) if player_pos else None
            location_name = player_data.get("location", "")
            facing = player_data.get("facing", "South")

            map_grid = format_map_grid(
                tiles,
                player_facing=facing,
                npcs=None,
                player_coords=player_coords,
                trim_padding=False,
                location_name=location_name
            )

            if not map_grid:
                logger.warning(f"Could not generate map grid to find object '{symbol}'")
                return None

            # Search for symbol in the grid
            for y, row in enumerate(map_grid):
                for x, cell in enumerate(row):
                    if cell == symbol:
                        symbol_name = {"S": "stairs", "D": "door", "N": "NPC", "T": "TV", "PC": "computer"}.get(symbol, symbol)
                        logger.info(f"🎯 Found {symbol_name} ({symbol}) at grid position ({x}, {y})")

                        # Convert grid position to world coordinates
                        # Grid is 15x15 centered on player, so center is at (7, 7)
                        center_x = len(map_grid[0]) // 2
                        center_y = len(map_grid) // 2

                        if player_coords:
                            world_x = player_coords[0] + (x - center_x)
                            world_y = player_coords[1] + (y - center_y)
                            logger.info(f"   World coordinates: ({world_x}, {world_y})")
                            return (world_x, world_y)
                        else:
                            # No player coords, return grid position
                            return (x, y)

            logger.warning(f"No object with symbol '{symbol}' found on current map")
            return None

        except Exception as e:
            logger.error(f"Error finding object '{symbol}': {e}")
            return None

    def find_stairs_on_map(self, game_state: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        """
        Find stairs (S symbol) on the current map.

        Returns coordinates of stairs if found, None otherwise.
        """
        return self.find_object_on_map(game_state, "S")

    def get_current_floor(self, game_state: Dict[str, Any]) -> int:
        """
        Determine current floor number from location name or map coordinates.

        Returns floor number (1, 2, etc.) or 1 if can't determine.
        """
        # First, check map bank/number for player's house specifically
        # Map (1, 0) = 1F, Map (1, 1) = 2F (player's house in Littleroot)
        map_info = game_state.get("map", {})
        if isinstance(map_info, dict):
            map_bank = map_info.get("bank", 0)
            map_number = map_info.get("number", 0)

            # Player's house multi-floor detection
            if map_bank == 1:
                if map_number == 0:
                    return 1  # 1F
                elif map_number == 1:
                    return 2  # 2F

        # Fallback to location string parsing
        location = game_state.get("player", {}).get("location", "")

        if "2F" in location or "2nd" in location.lower():
            return 2
        elif "3F" in location or "3rd" in location.lower():
            return 3
        elif "1F" in location or location:  # Default to 1st floor
            return 1

        return 1  # Default

    def add_objective(
        self,
        description: str,
        objective_type: str,
        target_value: Any = None,
        target_coords: Optional[Tuple[int, int]] = None,
        target_floor: Optional[int] = None,
        target_object: Optional[str] = None,
    ) -> str:
        """Add a new objective and return its ID"""
        obj_id = f"obj_{len(self.state.objectives)}_{int(datetime.now().timestamp())}"
        objective = Objective(
            id=obj_id,
            description=description,
            objective_type=objective_type,
            target_value=target_value,
            target_coords=target_coords,
            target_floor=target_floor,
            target_object=target_object,
        )
        self.state.objectives.append(objective)
        self.state.objectives_updated = True
        floor_info = f" floor {target_floor}" if target_floor else ""
        coords_info = f" at coords {target_coords}" if target_coords else ""
        object_info = f" object '{target_object}'" if target_object else ""
        logger.info(f"Added objective: {description}{floor_info}{coords_info}{object_info}")
        return obj_id

    def complete_objective(self, obj_id: str, progress_notes: str = ""):
        """Mark an objective as completed (storyline objectives cannot be manually completed)"""
        for obj in self.state.objectives:
            if obj.id == obj_id and not obj.completed:
                # Prevent manual completion of storyline objectives
                if obj.storyline:
                    logger.warning(
                        f"Cannot manually complete storyline objective: {obj.description}. These are verified by emulator milestones."
                    )
                    return False

                obj.completed = True
                obj.completed_at = datetime.now()
                obj.progress_notes = progress_notes
                self.state.objectives_updated = True
                logger.info(f"Completed objective: {obj.description}")
                return True
        return False

    def get_active_objectives(self) -> List[Objective]:
        """Get list of uncompleted objectives"""
        return [obj for obj in self.state.objectives if not obj.completed]

    def get_completed_objectives(self) -> List[Objective]:
        """Get list of completed objectives"""
        return [obj for obj in self.state.objectives if obj.completed]

    def check_objective_completion(self, game_state: Dict[str, Any]) -> List[str]:
        """Check if any objectives should be marked as completed based on game state"""
        completed_ids = []
        coords = self.get_player_coords(game_state)
        context = self.get_game_context(game_state)
        map_id = self.get_map_id(game_state)

        for obj in self.get_active_objectives():
            should_complete = False
            notes = ""

            if obj.objective_type == "location" and coords and obj.target_value:
                # Check if player reached target location
                # Note: target_value is a string (location name) for storyline objectives
                # Location objectives are completed via milestone verification, not coordinate checking
                # This section is for dynamically added coordinate-based objectives
                if isinstance(obj.target_value, (tuple, list)) and len(obj.target_value) == 2:
                    target_x, target_y = obj.target_value
                    if abs(coords[0] - target_x) <= 2 and abs(coords[1] - target_y) <= 2:
                        should_complete = True
                        notes = f"Reached location ({coords[0]}, {coords[1]})"

            elif obj.objective_type == "battle" and context == "battle":
                # Objective completed when battle starts
                should_complete = True
                notes = "Entered battle"

            elif obj.objective_type == "dialogue" and context == "dialogue":
                # Objective completed when dialogue starts
                should_complete = True
                notes = "Started dialogue"

            elif obj.objective_type == "map" and map_id and obj.target_value:
                # Check if player reached target map
                if map_id == obj.target_value:
                    should_complete = True
                    notes = f"Reached map {map_id}"

            if should_complete:
                self.complete_objective(obj.id, notes)
                completed_ids.append(obj.id)

        return completed_ids

    def check_storyline_milestones(self, game_state: Dict[str, Any]) -> List[str]:
        """Check emulator milestones and auto-complete corresponding storyline objectives"""
        completed_ids = []

        # Get milestones from the game state (if available)
        milestones = game_state.get("milestones", {})
        if not milestones:
            # No milestone data available, skip checking
            return completed_ids

        for obj in self.get_active_objectives():
            # Only check storyline objectives with milestone IDs
            if obj.storyline and obj.milestone_id and not obj.completed:
                # Check if the corresponding emulator milestone is completed
                milestone_completed = milestones.get(obj.milestone_id, {}).get("completed", False)

                if milestone_completed:
                    # Auto-complete the storyline objective
                    obj.completed = True
                    obj.completed_at = datetime.now()
                    obj.progress_notes = f"Auto-completed by emulator milestone: {obj.milestone_id}"
                    self.state.objectives_updated = True
                    completed_ids.append(obj.id)
                    logger.info(
                        f"✅ Auto-completed storyline objective via milestone {obj.milestone_id}: {obj.description}"
                    )

                    # Performance metrics: Log milestone completion (Phase 3.2)
                    self.performance_metrics.log_milestone(obj.milestone_id)

                    # Auto-save checkpoint when milestone is reached
                    self._save_milestone_checkpoint(obj.milestone_id, game_state)

        return completed_ids

    def _save_milestone_checkpoint(self, milestone_id: str, game_state: Dict[str, Any]):
        """Save an automatic checkpoint when a milestone is completed"""
        try:
            import os
            import requests
            from datetime import datetime

            # Create checkpoints directory if it doesn't exist
            checkpoints_dir = "checkpoints/milestones"
            os.makedirs(checkpoints_dir, exist_ok=True)

            # Generate filename: milestone_YYYYMMDD_HHMMSS.state
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{milestone_id}_{timestamp}.state"
            filepath = os.path.join(checkpoints_dir, filename)

            # Request server to save state via API
            server_url = os.getenv('SERVER_URL', 'http://localhost:8000')

            try:
                response = requests.post(
                    f"{server_url}/save_state",
                    json={"filepath": filepath},
                    timeout=10
                )

                if response.status_code == 200:
                    logger.info(f"💾 Milestone checkpoint saved: {filepath}")
                else:
                    logger.warning(f"⚠️  Failed to save milestone checkpoint: HTTP {response.status_code}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️  Cannot save milestone checkpoint: server not reachable ({e})")

        except Exception as e:
            logger.error(f"Failed to save milestone checkpoint for {milestone_id}: {e}")

    def detect_stuck_pattern(
        self, coords: Optional[Tuple[int, int]], context: str, game_state: Dict[str, Any] = None
    ) -> bool:
        """Detect if the agent appears to be stuck in a location/context"""
        # Don't trigger stuck detection during contexts where staying in place is expected
        if context in ["battle", "dialogue", "menu", "title"]:
            logger.debug(f"Skipping stuck detection - context: {context}")
            return False

        # Need valid coordinates for stuck detection
        if not coords or coords[0] is None or coords[1] is None:
            return False

        # Check for title sequence if game state is available
        if game_state:
            # Check if in title sequence (no player name or invalid coordinates)
            player_name = game_state.get("player", {}).get("name", "").strip()
            if not player_name or player_name == "????????":
                return False

            # Check if game state indicates title/intro
            game_state_value = game_state.get("game", {}).get("game_state", "").lower()
            if "title" in game_state_value or "intro" in game_state_value:
                return False

            # Check location for title sequence
            player_location = game_state.get("player", {}).get("location", "")
            if player_location == "TITLE_SEQUENCE":
                return False

        key = f"{coords[0]}_{coords[1]}_{context}"
        self.state.stuck_detection[key] = self.state.stuck_detection.get(key, 0) + 1

        # Consider stuck if we've been in the same location/context for 8+ consecutive steps
        return self.state.stuck_detection[key] >= 8

    def is_black_frame(self, frame) -> bool:
        """
        Check if the frame is mostly black (transition/loading screen).

        Args:
            frame: PIL Image or numpy array

        Returns:
            bool: True if frame is mostly black, False otherwise
        """
        try:
            # Convert to PIL Image if needed
            if hasattr(frame, "convert"):  # It's already a PIL Image
                img = frame
            elif hasattr(frame, "shape"):  # It's a numpy array
                img = Image.fromarray(frame)
            else:
                return False  # Unknown type, assume not black

            # Convert to numpy array for analysis
            img_array = np.array(img)

            # Calculate the mean brightness
            # For RGB images, average across all channels
            if len(img_array.shape) == 3:
                mean_brightness = np.mean(img_array)
            else:
                mean_brightness = np.mean(img_array)

            # Also check the standard deviation to catch completely uniform frames
            std_dev = np.std(img_array)

            # A frame is considered "black" if:
            # 1. Mean brightness is very low (< 10 out of 255)
            # 2. OR standard deviation is very low (< 5) indicating uniform color
            is_black = mean_brightness < 10 or (mean_brightness < 30 and std_dev < 5)

            if is_black:
                logger.debug(f"Black frame detected: mean_brightness={mean_brightness:.2f}, std_dev={std_dev:.2f}")

            return is_black

        except Exception as e:
            logger.warning(f"Error checking for black frame: {e}")
            return False  # On error, assume not black to continue processing

    def is_frame_similar(self, frame, similarity_threshold: float = 0.95) -> bool:
        """
        Check if current frame is very similar to the last frame.
        Uses perceptual hashing for fast comparison.

        Args:
            frame: Current frame (PIL Image or numpy array)
            similarity_threshold: Threshold for considering frames similar (0.0-1.0)

        Returns:
            bool: True if frame is similar enough to skip VLM processing
        """
        try:
            # Convert to PIL Image if needed
            if hasattr(frame, "convert"):  # It's already a PIL Image
                img = frame
            elif hasattr(frame, "shape"):  # It's a numpy array
                img = Image.fromarray(frame)
            else:
                return False  # Unknown type, can't compare

            # No previous frame to compare against
            if self.last_frame is None:
                self.last_frame = img
                return False

            # Quick numpy-based comparison (faster than perceptual hash)
            # Convert both to numpy arrays
            current_array = np.array(img)
            last_array = np.array(self.last_frame)

            # Check if shapes match
            if current_array.shape != last_array.shape:
                self.last_frame = img
                return False

            # Calculate pixel-wise difference
            # For GBA (240x160), this is very fast
            diff = np.abs(current_array.astype(float) - last_array.astype(float))
            mean_diff = np.mean(diff)
            max_diff = np.max(diff)

            # Frames are similar if:
            # 1. Mean difference is very small (< 5 out of 255)
            # 2. Max difference is not too large (< 50 out of 255)
            # This catches small animations but detects actual scene changes
            is_similar = mean_diff < 5 and max_diff < 50

            if is_similar:
                logger.debug(f"Similar frame detected: mean_diff={mean_diff:.2f}, max_diff={max_diff:.2f}")
                self.frame_skip_count += 1
            else:
                # Frame changed significantly, reset skip count
                self.frame_skip_count = 0
                self.last_frame = img

            return is_similar

        except Exception as e:
            logger.warning(f"Error checking frame similarity: {e}")
            return False  # On error, assume not similar to continue processing

    def get_relevant_history_summary(self, current_context: str, coords: Optional[Tuple[int, int]]) -> str:
        """Get a concise summary of relevant recent history (Phase 3.1 - with compression)"""
        # current_context and coords could be used for more sophisticated filtering in the future
        _ = current_context, coords  # Acknowledge unused parameters for now
        if not self.state.history:
            return "No previous history."

        # Use history compressor for efficient formatting (Phase 3.1)
        all_entries = list(self.state.history)
        compressed = self.history_compressor.compress_history(all_entries)

        return compressed

    def get_stuck_warning(
        self, coords: Optional[Tuple[int, int]], context: str, game_state: Dict[str, Any] = None
    ) -> str:
        """Generate warning text if stuck pattern detected"""
        # Never show stuck warning in title sequence
        if context == "title":
            return ""

        if self.detect_stuck_pattern(coords, context, game_state):
            return (
                "\n⚠️ WARNING: You appear to be stuck at this location/context. Try a different approach!\n"
                "💡 TIP: If you try an action like RIGHT but coordinates don't change from (X,Y) to (X+1,Y), there's likely an obstacle. Check the map around player P for walls (#) or other barriers blocking your path."
            )
        return ""

    def create_game_state_summary(self, game_state: Dict[str, Any]) -> str:
        """Create a concise summary of the current game state"""
        try:
            game_info = game_state.get("game", {})

            summary_parts = []

            # Player location
            coords = self.get_player_coords(game_state)
            if coords:
                summary_parts.append(f"Player at ({coords[0]}, {coords[1]})")

            # Map info
            map_id = self.get_map_id(game_state)
            if map_id:
                summary_parts.append(f"Map {map_id}")

            # Context-specific info
            context = self.get_game_context(game_state)
            if context == "battle":
                summary_parts.append("In battle")
            elif context == "dialogue":
                dialogue_text = game_info.get("dialogue", {}).get("text", "")
                if dialogue_text:
                    summary_parts.append(f"Dialogue: {dialogue_text}")

            return " | ".join(summary_parts) if summary_parts else "Unknown state"

        except Exception as e:
            logger.warning(f"Error creating game state summary: {e}")
            return "Error reading state"

    def step(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compatibility method for client that expects agent.step(game_state)

        Args:
            game_state: Complete game state dictionary (should include 'frame')

        Returns:
            Dictionary with 'action' and optional 'reasoning'
        """
        frame = game_state.get("frame")
        if frame is None:
            logger.error("🚫 No frame in game_state for SimpleAgent.step")
            return {"action": "WAIT", "reasoning": "No frame available"}

        action = self.process_step(frame, game_state)
        return {"action": action, "reasoning": "Simple agent decision"}

    def process_step(self, frame, game_state: Dict[str, Any]) -> str:
        """
        Main processing step for simple mode with history tracking

        Args:
            frame: Current game frame (PIL Image or similar)
            game_state: Complete game state dictionary

        Returns:
            Action string or list of actions
        """
        # CRITICAL: Check for map changes (warps, floor changes, entering buildings)
        # If map changed, clear navigation so VLM can see new environment first
        current_map_id = self.get_map_id(game_state)
        logger.warning(f"🗺️ CLAUDE DEBUG: Map ID check: current={current_map_id}, last={getattr(self, 'last_map_id', 'NOT_SET')}")
        if hasattr(self, 'last_map_id') and self.last_map_id is not None:
            if current_map_id != self.last_map_id:
                logger.warning(f"🗺️ MAP CHANGE DETECTED: {self.last_map_id} → {current_map_id}")
                # Clear navigation path so agent doesn't execute old path on new map
                if self.navigation_path or self.navigation_target:
                    logger.warning(f"🚫 Clearing navigation path due to map change (warp/stairs/door)")
                    self.navigation_path = None
                    self.navigation_target = None
        # Update last map ID for next step
        self.last_map_id = current_map_id

        # FAST TRACK: Handle title sequence efficiently (just press A to skip naming/intro)
        context = self.get_game_context(game_state)
        if context == "title":
            logger.info("⚡ Title sequence detected - pressing A to skip quickly")
            return "A"

        # SMART DIALOGUE HANDLING: Use memory reader detection for better decisions
        recent_actions = list(self.state.recent_actions)[-15:] if self.state.recent_actions else []
        a_count = recent_actions.count("A")  # Count recent A presses
        b_count = recent_actions.count("B")  # Count recent B presses

        # Check if dialogue is actively detected by memory reader
        dialogue_detected = game_state.get("game", {}).get("dialogue_detected", {})
        has_active_dialogue = dialogue_detected.get("has_dialogue", False)
        dialog_text = game_state.get("game", {}).get("dialog_text", "")

        # CRITICAL: Double-check dialogue is actually visible by checking context
        # If context is "overworld" but dialogue detected, it's likely residual/stale
        if context != "dialogue" and has_active_dialogue:
            # Context says overworld but dialogue detected - likely stale text
            logger.warning(f"⚠️ Context is '{context}' but dialogue detected - likely stale dialogue text, ignoring")
            has_active_dialogue = False

        # Also check confidence
        dialogue_confidence = dialogue_detected.get("confidence", 0.0)
        if dialogue_confidence < 0.5:
            has_active_dialogue = False
            logger.debug(f"Dialogue confidence too low ({dialogue_confidence}) - treating as no active dialogue")

        # YES/NO MENU DETECTION: Check if we're stuck in a Yes/No prompt (like clock setup)
        # These menus default to "NO" and need UP button to select "YES"
        if has_active_dialogue and dialog_text and a_count >= 3:
            # Check if dialogue text contains Yes/No pattern (case insensitive)
            dialog_lower = dialog_text.lower()
            is_yes_no_menu = any(pattern in dialog_lower for pattern in [
                "yes", "no", "set the clock", "is that okay", "is this ok"
            ])

            # Also check if we already pressed UP recently (to avoid UP spam)
            up_count = recent_actions.count("UP")

            if is_yes_no_menu and a_count >= 3 and up_count == 0:
                # Pressed A multiple times on Yes/No menu but haven't pressed UP yet
                logger.warning(f"🔼 YES/NO MENU DETECTED: Pressing UP to select YES (dialogue: {dialog_text[:50]})")
                return "UP"

        # DIALOGUE LOOP DETECTION: Check if we've seen the exact same dialogue text multiple times
        # AND we're pressing A repeatedly without the dialogue changing
        if has_active_dialogue and dialog_text and a_count >= 5:
            # Check last few history entries for same dialogue
            recent_history = list(self.state.history)[-15:]
            same_text_count = 0
            for entry in reversed(recent_history):
                if dialog_text in entry.game_state_summary:
                    same_text_count += 1
                else:
                    break

            # Only trigger escape if we've pressed A 5+ times AND seen same dialogue 3+ times
            # This means we're truly stuck in a loop, not just multi-box dialogue
            if same_text_count >= 3:
                logger.warning(
                    f"🚨 DIALOGUE LOOP DETECTED: Same dialogue text seen {same_text_count} times AND pressed A {a_count} times - trying to escape"
                )

                # Check current coordinates to decide escape direction
                coords = self.get_player_coords(game_state)

                # Try different escape strategies based on repeat count
                if same_text_count >= 6:
                    # Very stuck - try moving in multiple directions to escape the trigger zone
                    logger.warning("🚨 VERY STUCK: Trying to move away from dialogue trigger")
                    # Move in opposite direction if possible
                    if coords and coords[0] > 2:
                        return "LEFT"  # Move left if on right side
                    else:
                        return "RIGHT"  # Move right if on left side
                elif same_text_count >= 4:
                    # Moderately stuck - try moving DOWN to escape
                    logger.warning("🚨 MODERATELY STUCK: Trying to move DOWN")
                    return "DOWN"
                else:
                    # Slightly stuck - try moving UP to escape
                    logger.warning("🚨 SLIGHTLY STUCK: Trying to move UP")
                    return "UP"

        # If stuck pressing B repeatedly (dialogue won't close), try A instead
        if b_count >= 10:
            logger.warning(f"🚨 STUCK PRESSING B: Pressed B {b_count} times, trying A to advance/dismiss dialogue")
            return "A"

        # If in detected dialogue and pressed A many times (10+), wait for dialogue to process
        # Increased from 3 to 5 to avoid false positives from previous actions in history
        if context == "dialogue" and a_count >= 10:
            if has_active_dialogue:
                # Dialogue still active after 10 A presses - wait for it to process
                logger.info(f"⏳ Dialogue active, pressed A {a_count} times - waiting for dialogue to advance")
                return "WAIT"
            else:
                # Dialogue not active but context says dialogue - might be residual, try to move
                logger.warning(f"⚠️ Context says dialogue but memory says no dialogue - trying to move")
                return "DOWN"  # Try to move away

        # If in overworld but pressing A many times (likely stuck on NPC dialogue)
        if context == "overworld" and a_count >= 15:
            if has_active_dialogue:
                # Dialogue is actually active - wait
                logger.info(f"⏳ Overworld with active dialogue, pressed A {a_count} times - waiting")
                return "WAIT"
            else:
                # No active dialogue detected - try to move away from NPC
                logger.warning(f"🚨 Stuck pressing A in overworld, no dialogue detected - moving away")
                return "DOWN"

        # CRITICAL: Validate frame before any VLM processing
        if frame is None:
            logger.error("🚫 CRITICAL: SimpleAgent.process_step called with None frame - cannot proceed")
            return "WAIT"

        # Validate frame is a proper image
        if not (hasattr(frame, "save") or hasattr(frame, "shape")):
            logger.error(
                f"🚫 CRITICAL: SimpleAgent.process_step called with invalid frame type {type(frame)} - cannot proceed"
            )
            return "WAIT"

        # Additional PIL Image validation
        if hasattr(frame, "size"):
            width, height = frame.size
            if width <= 0 or height <= 0:
                logger.error(
                    f"🚫 CRITICAL: SimpleAgent.process_step called with invalid frame size {width}x{height} - cannot proceed"
                )
                return "WAIT"

        # Check for black frame (transition screen)
        if self.is_black_frame(frame):
            logger.info("⏳ Black frame detected (likely a transition), waiting for next frame...")
            return "WAIT"  # Return WAIT to skip this frame and wait for the next one

        # OPTIMIZATION: Check for similar frame (Phase 1.1)
        # Skip VLM processing if frame hasn't changed significantly
        # BUT: Only skip if we're not in a critical context (battle, dialogue)
        # AND: Only skip up to 2 frames max to avoid missing important changes
        if context not in ["battle", "dialogue", "title"] and self.frame_skip_count < 2:
            if self.is_frame_similar(frame):
                # Frame is very similar to last one, reuse last action
                if self.last_vlm_action:
                    logger.info(
                        f"⚡ Frame skip optimization: Reusing last action '{self.last_vlm_action}' "
                        f"(skip count: {self.frame_skip_count})"
                    )
                    # Performance metrics: Log frame skip (Phase 3.2)
                    self.performance_metrics.log_frame_skip()

                    # Add to recent actions for tracking
                    self.state.recent_actions.append(self.last_vlm_action)
                    return self.last_vlm_action
                else:
                    # No previous action to reuse, proceed with VLM
                    logger.debug("Similar frame but no previous action, proceeding with VLM")
        else:
            # Reset frame skip tracking when in critical contexts
            if context in ["battle", "dialogue", "title"]:
                self.frame_skip_count = 0

        try:
            # Increment step counter
            self.state.step_counter += 1

            # Get current state info
            coords = self.get_player_coords(game_state)
            context = self.get_game_context(game_state)
            map_id = self.get_map_id(game_state)

            # Performance metrics: Track battle state transitions (Phase 3.2)
            if context == "battle" and self.last_battle_state != "battle":
                # Battle just started
                self.performance_metrics.log_battle_start()
                logger.info("📊 Battle started - tracking battle metrics")
            elif context != "battle" and self.last_battle_state == "battle":
                # Battle just ended - try to determine outcome
                # For now, we can't determine win/loss without more info, but we log the transition
                logger.info("📊 Battle ended - no outcome tracking yet (needs enhancement)")
            self.last_battle_state = context

            # CRITICAL: Clean stale dialogue from game_state before formatting for VLM
            # If context is "overworld", it means dialogue is stale/residual
            if context == "overworld":
                # Clear the has_dialogue flag so stale dialogue isn't shown to VLM
                if "game" in game_state and "dialogue_detected" in game_state["game"]:
                    game_state["game"]["dialogue_detected"]["has_dialogue"] = False
                    logger.debug("Cleared stale dialogue flag for VLM (context is overworld)")

            # Format the current state for LLM (includes movement preview)
            formatted_state = format_state_for_llm(game_state)

            # Get movement memory for the current area
            movement_memory = ""
            if coords:
                movement_memory = self.get_area_movement_memory(coords)

            # Get strategic memory for current location (Phase 2.1)
            strategic_memory_text = ""
            try:
                current_location = game_state.get('player', {}).get('location', '')
                strategic_memory_text = self.strategic_memory.format_memory_for_prompt(current_location)
            except Exception as e:
                logger.warning(f"Failed to format strategic memory: {e}")

            # Get speedrun progress (Phase 2.2)
            speedrun_progress_text = ""
            try:
                # Get current milestones from game state
                milestones = game_state.get('milestones', {})
                speedrun_progress_text = self.speedrun_router.format_progress_for_prompt(
                    current_milestones=milestones,
                    current_actions=self.state.step_counter
                )
            except Exception as e:
                logger.warning(f"Failed to format speedrun progress: {e}")

            # Check for objective completion first
            self.check_objective_completion(game_state)

            # Check storyline milestones and auto-complete objectives
            self.check_storyline_milestones(game_state)

            # CRITICAL: If in real dialogue, clear any navigation and let dialogue handling take priority
            dialogue_detected = game_state.get("game", {}).get("dialogue_detected", {})
            has_active_dialogue = dialogue_detected.get("has_dialogue", False)
            if has_active_dialogue and context == "dialogue":
                # Clear navigation if we're in active dialogue - can't navigate during dialogue
                if self.navigation_path:
                    logger.info("⏸️  Pausing navigation - active dialogue detected, must dismiss first")
                    # Don't clear fully, just pause - we'll resume after dialogue
                    self.navigation_path = None  # Clear so we recalculate after dialogue

            # AUTO-NAVIGATION: Check if we have an active navigation path
            # BUT skip auto-navigation in special locations (MOVING_VAN, INTRO) or critical contexts (dialogue, menu, battle)
            location = game_state.get('player', {}).get('location', '')
            if location in ['MOVING_VAN', 'INTRO']:
                # Cancel any active navigation in special locations
                if self.navigation_path or self.navigation_target:
                    logger.info(f"🚫 Cancelling auto-navigation in special location: {location}")
                    self.navigation_path = []
                    self.navigation_target = None
            elif context in ["dialogue", "menu", "battle"]:
                # CRITICAL: Don't continue navigation during dialogue/menu/battle
                # Clear the path so we don't try to navigate
                if self.navigation_path or self.navigation_target:
                    logger.info(f"⏸️  Pausing auto-navigation - in {context} context")
                    self.navigation_path = None  # Clear path
                    # Don't clear target - we can resume later
            else:
                # Normal auto-navigation (outside special locations and critical contexts)
                nav_action = self.get_next_navigation_action(game_state)
                if nav_action:
                    logger.info(f"🧭 Auto-navigation: {nav_action} toward {self.navigation_target}")
                    # Add navigation action to history for tracking
                    self.state.recent_actions.append(nav_action)
                    # Add to history entry
                    history_entry = HistoryEntry(
                        timestamp=datetime.now(),
                        player_coords=coords,
                        map_id=map_id,
                        context=context,
                        action_taken=nav_action,
                        game_state_summary=f"Auto-navigation: {nav_action} toward {self.navigation_target}",
                    )
                    self.state.history.append(history_entry)
                    return nav_action

            # Get active objectives (needed for both navigation and LLM prompt)
            active_objectives = self.get_active_objectives()
            logger.warning(f"🎯 CLAUDE DEBUG: Active objectives count: {len(active_objectives)}")
            if active_objectives:
                for obj in active_objectives:
                    logger.warning(f"  - {obj.description} (coords={obj.target_coords}, floor={obj.target_floor})")

            # AUTO-NAVIGATION START: Check if current objective has target coordinates
            if active_objectives and coords:
                # Check if we're super stuck (same position for 10+ steps)
                # BUT: Do NOT check during dialogue/menu/battle - those contexts naturally keep you in place
                super_stuck = False
                if context not in ["dialogue", "menu", "battle"] and len(self.state.history) >= 10:
                    recent_coords = [e.player_coords for e in list(self.state.history)[-10:] if e.player_coords]
                    if len(recent_coords) >= 10 and len(set(recent_coords)) == 1:
                        super_stuck = True
                        logger.warning(
                            f"🆘 SUPER STUCK: Same position {coords} for 10+ steps in overworld"
                        )

                # Find first objective with target_coords OR target_object that needs navigation
                for obj in active_objectives:
                    # Check if objective has navigation target (coords or object symbol)
                    has_navigation_target = (obj.target_coords or obj.target_object) and not obj.completed
                    logger.debug(f"  Checking obj '{obj.description}': has_nav_target={has_navigation_target}")

                    if has_navigation_target:
                        # Resolve target coordinates
                        # Priority: explicit target_coords > target_object lookup
                        navigation_target = None

                        if obj.target_coords:
                            navigation_target = obj.target_coords
                        elif obj.target_object:
                            # Find object on map by symbol
                            object_coords = self.find_object_on_map(game_state, obj.target_object)
                            if object_coords:
                                navigation_target = object_coords
                                logger.info(f"🎯 Resolved target_object '{obj.target_object}' to coordinates {object_coords}")
                            else:
                                # Object not found yet
                                # For cutscene objectives, WAIT instead of using VLM (saves API calls)
                                if obj.objective_type == "cutscene":
                                    logger.info(f"🎬 Cutscene objective: waiting for '{obj.target_object}' to appear in memory (no VLM needed)")
                                    return "WAIT"
                                else:
                                    # Non-cutscene: let VLM handle it
                                    logger.info(f"⏭️  Object '{obj.target_object}' not found on map - letting VLM handle navigation")
                                    break

                        if not navigation_target:
                            break

                        # Check if we're already at the target OR adjacent to it
                        # Adjacent means within 1 tile (for interacting with objects on walls)
                        distance_to_target = abs(coords[0] - navigation_target[0]) + abs(coords[1] - navigation_target[1])
                        is_adjacent = distance_to_target == 1

                        if is_adjacent:
                            # We're right next to the target (e.g., standing in front of clock on wall)
                            # Let VLM handle the interaction instead of pathfinding
                            logger.info(f"🎯 Adjacent to target {navigation_target} - letting VLM handle interaction")
                            break

                        if coords != navigation_target:
                            # MULTI-FLOOR NAVIGATION: Check if we need to go to stairs first

                            if obj.target_floor:
                                current_floor = self.get_current_floor(game_state)
                                logger.warning(f"🏢 CLAUDE DEBUG: Floor check: Current floor = {current_floor}, Target floor = {obj.target_floor}")

                                if current_floor != obj.target_floor:
                                    # Need to change floors - navigate to stairs first
                                    stairs_coords = self.find_stairs_on_map(game_state)

                                    if stairs_coords:
                                        navigation_target = stairs_coords
                                        logger.info(
                                            f"🪜 Multi-floor navigation: Currently on floor {current_floor}, need floor {obj.target_floor}"
                                        )
                                        logger.info(f"🪜 Navigating to stairs at {stairs_coords} first")
                                    else:
                                        # Can't find stairs, let VLM handle it
                                        logger.info(
                                            f"⏭️  No stairs found on map - letting VLM handle navigation to floor {obj.target_floor}"
                                        )
                                        break

                            # Check if we're in special location where auto-navigation should be disabled
                            location = game_state.get('player', {}).get('location', '')
                            if location in ['MOVING_VAN', 'INTRO']:
                                logger.info(f"🚫 Skipping auto-navigation in special location: {location} (will use VLM instead)")
                                break  # Skip auto-navigation, let VLM handle it

                            # Check if we're in dialogue/menu context - don't auto-navigate during these
                            # Don't allow super_stuck to override dialogue - dialogue must complete first!
                            logger.warning(f"🎮 CLAUDE DEBUG: Context check: context='{context}', coords={coords}, target={navigation_target}")
                            if context not in ["dialogue", "menu", "battle"]:
                                logger.warning(f"✅ CLAUDE DEBUG: Context '{context}' allows auto-navigation")
                                logger.warning(f"🎯 CLAUDE DEBUG: Objective '{obj.description}' has target coords {obj.target_coords}")
                                logger.warning(f"📍 CLAUDE DEBUG: Current position: {coords}, Target: {navigation_target}")

                                # Start navigation if not already navigating
                                logger.warning(f"🚀 CLAUDE DEBUG: About to call start_navigation({navigation_target})...")
                                if self.start_navigation(navigation_target, game_state):
                                    # Return first action from the calculated path
                                    nav_action = self.get_next_navigation_action(game_state)
                                    if nav_action:
                                        logger.info(f"🧭 Starting auto-navigation: {nav_action}")
                                        # Add navigation action to history for tracking
                                        self.state.recent_actions.append(nav_action)
                                        # Add to history entry
                                        history_entry = HistoryEntry(
                                            timestamp=datetime.now(),
                                            player_coords=coords,
                                            map_id=map_id,
                                            context=context,
                                            action_taken=nav_action,
                                            game_state_summary=f"Starting auto-navigation: {nav_action} toward {obj.target_coords}",
                                        )
                                        self.state.history.append(history_entry)
                                        return nav_action
                            else:
                                logger.info(f"⏸️  Auto-navigation blocked: context='{context}' (need overworld)")
                        break  # Only handle one objective at a time

            # Get relevant history and stuck detection
            history_summary = self.get_relevant_history_summary(context, coords)
            stuck_warning = self.get_stuck_warning(coords, context, game_state)

            # Compress recent actions (Phase 3.1)
            recent_actions_list = list(self.state.recent_actions) if self.state.recent_actions else []
            recent_actions_str = self.history_compressor.compress_action_list(
                recent_actions_list,
                max_display=self.actions_display_count
            )

            # Format objectives for LLM (active_objectives already retrieved above)
            completed_objectives_list = self.get_completed_objectives()
            objectives_summary = self._format_objectives_for_llm(active_objectives, completed_objectives_list)

            # FRONTIER-BASED EXPLORATION: Detect exploration targets (only in overworld)
            frontier_suggestions = ""
            if context == "overworld" and coords:
                try:
                    from utils.frontier_detection import FrontierDetector

                    # Initialize detector
                    frontier_detector = FrontierDetector(
                        max_search_depth=50,
                        max_frontiers_returned=20,
                        distance_penalty_factor=0.5,
                        enable_randomization=True
                    )

                    # Get current objective coords for bonus scoring
                    current_objective_coords = None
                    if active_objectives:
                        for obj in active_objectives:
                            if obj.target_coords and not obj.completed:
                                current_objective_coords = obj.target_coords
                                break

                    # Detect frontiers
                    frontiers = frontier_detector.detect_frontiers(
                        game_state=game_state,
                        player_pos=coords,
                        unreachable=self.unreachable_frontiers,
                        current_objective=current_objective_coords
                    )

                    # Cache frontiers for FRONTIER_N command parsing
                    self.last_detected_frontiers = frontiers

                    # Format for prompt
                    if frontiers:
                        frontier_suggestions = frontier_detector.format_frontiers_for_prompt(
                            frontiers, max_display=5
                        )
                        logger.info(f"🎯 Detected {len(frontiers)} frontiers for exploration")
                    else:
                        logger.debug("No frontiers detected (fully explored or no map data)")

                except Exception as e:
                    logger.warning(f"Frontier detection failed: {e}", exc_info=True)
                    frontier_suggestions = ""

            # Generate battle analysis if in battle (Phase 1.3 optimization)
            battle_analysis = ""
            if context == "battle":
                try:
                    battle_info = game_data.get('battle_info', {})
                    player_pokemon = battle_info.get('player_pokemon', {})
                    opponent_pokemon = battle_info.get('opponent_pokemon', {})

                    if player_pokemon and opponent_pokemon:
                        # Get moves data
                        moves = player_pokemon.get('moves', [])
                        move_pp = player_pokemon.get('move_pp', [])

                        # Build move data structures for battle analyzer
                        available_moves = []
                        for i, move_name in enumerate(moves):
                            if move_name and move_name.strip():
                                # Note: Move type and power would ideally come from game data
                                # For now, battle analyzer will use move database
                                available_moves.append({
                                    'name': move_name,
                                    'type': 'Normal',  # Placeholder - would need move database
                                    'power': 50,  # Placeholder
                                    'pp': move_pp[i] if i < len(move_pp) else 0
                                })

                        # Get party for switch analysis
                        party = player_data.get('party', [])

                        # Generate battle analysis
                        battle_analysis = self.battle_analyzer.format_battle_analysis(
                            player_pokemon,
                            opponent_pokemon,
                            available_moves,
                            party
                        )
                        logger.info(f"Generated battle analysis:\n{battle_analysis}")
                except Exception as e:
                    logger.warning(f"Failed to generate battle analysis: {e}")
                    battle_analysis = ""

            # Check if using local/compact mode for smaller models
            use_compact_prompt = os.getenv('COMPACT_PROMPT', 'false').lower() == 'true'

            # Add special hint for MOVING_VAN intro
            moving_van_hint = ""
            try:
                location = game_state.get('player', {}).get('location', '')
                if location == 'MOVING_VAN':
                    moving_van_hint = """
⚠️ SPECIAL LOCATION HINT - MOVING VAN INTRO:
You are in the moving van at the START of the game. To exit the van and begin the game:
- Move RIGHT to reach the exit/door of the van
- The map shows limited data during this cutscene - trust the visual frame
- Do NOT get stuck moving UP/DOWN - you need to go RIGHT to exit
- Once you exit RIGHT, the intro will complete and you'll be in your new house
"""
            except Exception:
                pass

            # Build pathfinding rules section (only if not in title sequence)
            pathfinding_rules = ""
            if context != "title" and not use_compact_prompt:
                pathfinding_rules = """
🚨 PATHFINDING RULES:
1. **SINGLE STEP FIRST**: Always prefer single actions (UP, DOWN, LEFT, RIGHT, A, B) unless you're 100% certain about multi-step paths
2. **CHECK EVERY STEP**: Before chaining movements, verify EACH step in your sequence using the MOVEMENT PREVIEW and map
3. **BLOCKED = STOP**: If ANY step shows BLOCKED in the movement preview, the entire sequence will fail
4. **NO BLIND CHAINS**: Never chain movements through areas you can't see or verify as walkable
5. **PERFORM PATHFINDING**: Find a path to a target location (X',Y') from the player position (X,Y) on the map. DO NOT TRAVERSE THROUGH OBSTACLES (#) -- it will not work.

💡 SMART MOVEMENT STRATEGY:
- Use MOVEMENT PREVIEW to see exactly what happens with each direction
- If your target requires multiple steps, plan ONE step at a time
- Only chain 2-3 moves if ALL intermediate tiles are confirmed WALKABLE
- When stuck, try a different direction rather than repeating the same blocked move
- After moving in a direction, you will be facing that direction for interactions with NPCs, etc.

EXAMPLE - DON'T DO THIS:
❌ "I want to go right 5 tiles" → "RIGHT, RIGHT, RIGHT, RIGHT, RIGHT" (may hit wall on step 2!)

EXAMPLE - DO THIS INSTEAD:
✅ Check movement preview → "RIGHT shows (X+1,Y) WALKABLE" → "RIGHT" (single safe step)
✅ Next turn, check again → "RIGHT shows (X+2,Y) WALKABLE" → "RIGHT" (another safe step)

💡 SMART NAVIGATION:
- The Player's sprite in the visual frame is located at the coordinates (X,Y) in the game state. Objects in the visual frame should be represented in relation to the Player's sprite.
- Check the VISUAL FRAME for NPCs (people/trainers) and other objects like clocks before moving - they're not always on the map! NPCs may block movement even when the movement preview shows them as walkable.
- Review MOVEMENT MEMORY for locations where you've failed to move before
- Only explore areas marked with ? (these are confirmed explorable edges)
- Avoid areas surrounded by # (walls) - they're fully blocked
- Use doors (D), stairs (S), or walk around obstacles when pathfinding suggests it

💡 NPC & OBSTACLE HANDLING:
- If you see NPCs in the image, avoid walking into them or interact with A/B if needed
- If a movement fails (coordinates don't change), that location likely has an NPC or obstacle
- Use your MOVEMENT MEMORY to remember problem areas and plan around them
- NPCs can trigger battles or dialogue, which may be useful for objectives
"""

            # Create prompt - use compact mode for local models or full mode for cloud (Phase 1.2)
            if use_compact_prompt:
                # COMPACT MODE for local models (reduced token count)
                prompt = get_compact_prompt(
                    context=context,
                    coords=coords,
                    recent_actions=recent_actions_str,
                    objectives=objectives_summary,
                    formatted_state=formatted_state + "\n" + movement_memory
                )
            else:
                # FULL MODE for cloud models (context-aware detailed prompt)
                # Combine movement memory, strategic memory, speedrun progress, and collision warnings
                combined_memory = movement_memory
                if strategic_memory_text:
                    combined_memory += "\n\n" + strategic_memory_text if combined_memory else strategic_memory_text
                if speedrun_progress_text:
                    combined_memory += "\n\n" + speedrun_progress_text if combined_memory else speedrun_progress_text

                # Add collision handler warnings (Phase 5.1)
                if coords:
                    collision_warning = self.collision_handler.get_collision_warning(coords)
                    if collision_warning:
                        combined_memory += "\n\n" + collision_warning if combined_memory else collision_warning

                    # Add safe directions if some are blocked
                    safe_directions = self.collision_handler.get_safe_directions(coords)
                    if len(safe_directions) < 4:
                        blocked_dirs = set(["UP", "DOWN", "LEFT", "RIGHT"]) - set(safe_directions)
                        safe_warning = f"⚠️ BLOCKED DIRECTIONS at {coords}: {', '.join(sorted(blocked_dirs))} are unreachable. Safe: {', '.join(sorted(safe_directions))}"
                        combined_memory += "\n" + safe_warning if combined_memory else safe_warning

                prompt = get_full_prompt(
                    context=context,
                    coords=coords,
                    recent_actions=recent_actions_str,
                    history_summary=history_summary,
                    objectives=objectives_summary,
                    formatted_state=formatted_state,
                    actions_count=self.actions_display_count,
                    history_count=self.history_display_count,
                    frontier_suggestions=frontier_suggestions if frontier_suggestions else "",
                    battle_analysis=battle_analysis if battle_analysis else "",
                    movement_memory=combined_memory if combined_memory else "",
                    stuck_warning=stuck_warning if stuck_warning else ""
                )

            # Apply model-specific optimizations (Phase 3.3)
            prompt = self.model_optimizer.optimize_prompt(prompt, context)

            # Print complete prompt to terminal for debugging
            print("\n" + "=" * 120)
            print("🤖 SIMPLE AGENT PROMPT SENT TO VLM:")
            print("=" * 120)

            # Print prompt in chunks to avoid terminal truncation
            sys.stdout.write(prompt)
            sys.stdout.write("\n")
            sys.stdout.flush()

            print("=" * 120)
            print("🤖 END OF SIMPLE AGENT PROMPT")
            print("=" * 120 + "\n")
            sys.stdout.flush()

            # Make VLM call - double-check frame validation before VLM
            if frame and (hasattr(frame, "save") or hasattr(frame, "shape")):
                print("🔍 Making VLM call...")
                try:
                    # Performance metrics: Track VLM call timing (Phase 3.2)
                    import time
                    vlm_start_time = time.time()

                    response = self.vlm.get_query(frame, prompt, "simple_mode")

                    vlm_duration = time.time() - vlm_start_time
                    self.performance_metrics.log_vlm_call(vlm_duration)

                    print(
                        f"🔍 VLM response received: {response[:100]}..."
                        if len(response) > 100
                        else f"🔍 VLM response: {response}"
                    )
                except Exception as e:
                    print(f"❌ VLM call failed: {e}")
                    return "WAIT"
            else:
                logger.error("🚫 CRITICAL: About to call VLM but frame validation failed - this should never happen!")
                return "WAIT"

            # Extract action(s) from structured response
            actions, reasoning = self._parse_structured_response(response, game_state)

            # CRITICAL SAFETY CHECK: Prevent movement during active dialogue
            dialogue_detected = game_state.get("game", {}).get("dialogue_detected", {})
            has_active_dialogue = dialogue_detected.get("has_dialogue", False)

            if has_active_dialogue:
                # Dialogue is active - only allow A, B, or WAIT
                movement_actions = ["UP", "DOWN", "LEFT", "RIGHT"]

                # Check if action is a movement command
                is_movement = False
                if isinstance(actions, list):
                    is_movement = any(action in movement_actions for action in actions)
                elif isinstance(actions, str):
                    is_movement = actions in movement_actions

                if is_movement:
                    logger.warning(
                        f"⚠️ DIALOGUE SAFETY: Agent attempted {actions} during active dialogue. "
                        f"Overriding to 'A' to dismiss dialogue."
                    )
                    print(
                        f"\n🚨 DIALOGUE SAFETY OVERRIDE: Movement command {actions} blocked during dialogue.\n"
                        f"   Automatically pressing 'A' to dismiss dialogue instead.\n"
                    )
                    actions = "A"
                    reasoning = "OVERRIDDEN: Dialogue must be dismissed before movement"

            # Check for failed movement by comparing previous coordinates
            if len(self.state.history) > 0:
                prev_coords = self.state.history[-1].player_coords
                if prev_coords and coords:
                    # If coordinates didn't change and we attempted a movement, record it as failed
                    if (
                        prev_coords == coords
                        and isinstance(actions, list)
                        and len(actions) > 0
                        and actions[0] in ["UP", "DOWN", "LEFT", "RIGHT"]
                    ):
                        self.record_failed_movement(coords, actions[0], "movement_blocked")
                    elif (
                        prev_coords == coords
                        and isinstance(actions, str)
                        and actions in ["UP", "DOWN", "LEFT", "RIGHT"]
                    ):
                        self.record_failed_movement(coords, actions, "movement_blocked")

            # Record this step in history with reasoning
            game_state_summary = self.create_game_state_summary(game_state)
            action_with_reasoning = f"{actions} | Reasoning: {reasoning}" if reasoning else str(actions)
            history_entry = HistoryEntry(
                timestamp=datetime.now(),
                player_coords=coords,
                map_id=map_id,
                context=context,
                action_taken=action_with_reasoning,
                game_state_summary=game_state_summary,
            )
            self.state.history.append(history_entry)

            # Update recent actions
            if isinstance(actions, list):
                self.state.recent_actions.extend(actions)
                # Increment movement memory action counter by number of actions
                self.state.movement_memory_action_counter += len(actions)
            else:
                self.state.recent_actions.append(actions)
                # Increment movement memory action counter
                self.state.movement_memory_action_counter += 1

            # Check if we should clear movement memory
            if (
                self.movement_memory_clear_interval > 0
                and self.state.movement_memory_action_counter >= self.movement_memory_clear_interval
            ):
                logger.info(
                    f"🧹 Movement memory clear triggered after {self.state.movement_memory_action_counter} actions"
                )
                # Use partial clear to keep some recent memory
                self.clear_movement_memory(partial=True)

            # Reset stuck detection for other locations when we move
            if coords:
                keys_to_reset = [
                    k for k in self.state.stuck_detection.keys() if not k.startswith(f"{coords[0]}_{coords[1]}")
                ]
                for key in keys_to_reset:
                    if self.state.stuck_detection[key] > 0:
                        self.state.stuck_detection[key] = max(0, self.state.stuck_detection[key] - 1)

            # Update server with agent step and metrics (for agent thinking display)
            update_server_metrics()

            # Store last VLM action for frame skip optimization (Phase 1.1)
            if isinstance(actions, list) and len(actions) > 0:
                self.last_vlm_action = actions[0]  # Store first action of sequence
            else:
                self.last_vlm_action = actions

            # Performance metrics: Log action taken (Phase 3.2)
            action_str = str(actions) if isinstance(actions, str) else ', '.join(actions) if isinstance(actions, list) else str(actions)
            self.performance_metrics.log_action(action_str, context, duration=0.0)

            # Performance metrics: Take snapshot if needed (Phase 3.2)
            current_location = game_state.get('player', {}).get('location', 'UNKNOWN')
            self.performance_metrics.maybe_take_snapshot(current_location)

            # Collision handler: Record movement for collision tracking (Phase 5.1)
            # This happens BEFORE the action is executed, so we track based on the LAST action's result
            # We'll track the position change on the NEXT call
            # Store current position for next iteration's collision detection
            if coords and coords[0] is not None and coords[1] is not None:
                # Check if we moved since last action
                if hasattr(self, '_last_tracked_position') and self._last_tracked_position is not None:
                    previous_coords = self._last_tracked_position
                    current_coords = coords

                    # Determine if movement occurred
                    moved = (current_coords != previous_coords)

                    # Get the last action that was executed
                    last_action = self._last_tracked_action if hasattr(self, '_last_tracked_action') else None

                    if last_action in ["UP", "DOWN", "LEFT", "RIGHT"]:
                        # Record the movement result
                        collision_result = self.collision_handler.record_movement(
                            current_position=previous_coords,  # Where we were when we tried to move
                            action=last_action,
                            moved=moved
                        )

                        # Log collision events
                        if collision_result["collision_detected"]:
                            logger.debug(
                                f"🚧 Collision at {previous_coords}: {collision_result['consecutive_collisions']} consecutive"
                            )

                        # Check for abandonment signal
                        if collision_result["should_abandon"]:
                            logger.warning(
                                f"❌ Path abandoned at {previous_coords} after {collision_result['consecutive_collisions']} collisions"
                            )

                # Store current position and action for next iteration
                self._last_tracked_position = coords
                self._last_tracked_action = actions if isinstance(actions, str) else (actions[0] if actions else None)

            return actions

        except Exception as e:
            logger.error(f"Error in simple agent processing: {e}")
            return ["A"]  # Default safe action as list

    def _parse_actions(self, response: str, game_state: Dict[str, Any] = None) -> List[str]:
        """Parse action response from LLM into list of valid actions"""
        response_upper = response.upper().strip()
        valid_actions = ["A", "B", "START", "SELECT", "UP", "DOWN", "LEFT", "RIGHT", "WAIT"]

        # Check for FRONTIER_N commands first (e.g., FRONTIER_1, FRONTIER_2, etc.)
        import re
        frontier_match = re.search(r'FRONTIER[_\s](\d+)', response_upper)
        if frontier_match and game_state:
            frontier_index = int(frontier_match.group(1))
            logger.info(f"🎯 Detected FRONTIER_{frontier_index} command from VLM")

            # Trigger navigation to the selected frontier
            action = self._navigate_to_frontier_index(frontier_index, game_state)
            if action:
                return [action]
            else:
                logger.warning(f"Failed to navigate to FRONTIER_{frontier_index}, falling back to normal parsing")

        # Parse multiple actions (could be comma or space separated)
        actions_found = []
        # Replace commas with spaces for consistent parsing
        response_clean = response_upper.replace(",", " ").replace(".", " ")
        tokens = response_clean.split()

        for token in tokens:
            if token in valid_actions:
                actions_found.append(token)
                if len(actions_found) >= 10:  # Max 10 actions
                    break

        # Validate movement sequences if we have game state
        if game_state and len(actions_found) > 1:
            # Check if this is a movement sequence
            movement_actions = [a for a in actions_found if a in ["UP", "DOWN", "LEFT", "RIGHT"]]
            if movement_actions:
                # Validate the movement sequence
                is_valid, reason = self.validate_movement_sequence(movement_actions, game_state)
                if not is_valid:
                    logger.warning(f"Movement sequence validation failed: {reason}")
                    # Only take the first movement if sequence is invalid
                    if movement_actions:
                        actions_found = [movement_actions[0]]
                        logger.info(f"Reduced to single movement: {actions_found[0]}")

        # If no valid actions found, use default
        if not actions_found:
            actions_found = ["A"]

        return actions_found

    def _format_objectives_for_llm(
        self, active_objectives: List[Objective], completed_objectives: List[Objective]
    ) -> str:
        """Format objectives for LLM consumption"""
        lines = []

        if active_objectives:
            lines.append("🎯 ACTIVE OBJECTIVES:")
            for i, obj in enumerate(active_objectives[:5], 1):  # Show top 5 active
                target_str = f" (Target: {obj.target_value})" if obj.target_value else ""
                lines.append(f"  {i}. [{obj.objective_type}] {obj.description}{target_str} [ID: {obj.id}]")
        else:
            lines.append("🎯 ACTIVE OBJECTIVES: None - Consider setting some goals!")

        if completed_objectives:
            recent_completed = completed_objectives[-3:]  # Show last 3 completed
            lines.append("✅ RECENTLY COMPLETED:")
            for obj in recent_completed:
                lines.append(f"  ✓ [{obj.objective_type}] {obj.description}")

        return "\n".join(lines)

    def _parse_structured_response(self, response: str, game_state: Dict[str, Any] = None) -> Tuple[List[str], str]:
        """Parse structured chain-of-thought response and extract actions and reasoning"""
        try:
            # Extract sections from structured response
            analysis = ""
            objectives_section = ""
            plan = ""
            reasoning = ""
            actions = []

            # Split response into lines for processing
            lines = response.split("\n")
            current_section = None

            for line in lines:
                line = line.strip()

                # Identify section headers
                if line.upper().startswith("ANALYSIS:"):
                    current_section = "analysis"
                    analysis = line[9:].strip()  # Remove "ANALYSIS:" prefix
                elif line.upper().startswith("OBJECTIVES:"):
                    current_section = "objectives"
                    objectives_section = line[11:].strip()  # Remove "OBJECTIVES:" prefix
                elif line.upper().startswith("PLAN:"):
                    current_section = "plan"
                    plan = line[5:].strip()  # Remove "PLAN:" prefix
                elif line.upper().startswith("REASONING:"):
                    current_section = "reasoning"
                    reasoning = line[10:].strip()  # Remove "REASONING:" prefix
                elif line.upper().startswith("ACTION:"):
                    current_section = "action"
                    # Extract actions from this line
                    action_text = line[7:].strip()  # Remove "ACTION:" prefix
                    if action_text:  # Only parse if there's content
                        actions = self._parse_actions(action_text, game_state)
                elif line and current_section:
                    # Continue content of current section
                    if current_section == "analysis":
                        analysis += " " + line
                    elif current_section == "objectives":
                        objectives_section += " " + line
                    elif current_section == "plan":
                        plan += " " + line
                    elif current_section == "reasoning":
                        reasoning += " " + line
                    elif current_section == "action":
                        # Additional action parsing from action section content
                        if line.strip():  # Only process non-empty lines
                            additional_actions = self._parse_actions(line, game_state)
                            actions.extend(additional_actions)
                            if len(actions) >= 10:  # Max 10 actions
                                actions = actions[:10]
                                break

            # Process objectives if mentioned
            if objectives_section:
                self._process_objectives_from_response(objectives_section)

            # If no actions found in structured format, fall back to parsing entire response
            if not actions:
                actions = self._parse_actions(response, game_state)

            # Create concise reasoning summary
            reasoning_parts = []
            if analysis:
                reasoning_parts.append(f"Analysis: {analysis}")
            if objectives_section:
                reasoning_parts.append(f"Objectives: {objectives_section}")
            if plan:
                reasoning_parts.append(f"Plan: {plan}")
            if reasoning:
                reasoning_parts.append(f"Reasoning: {reasoning}")

            full_reasoning = " | ".join(reasoning_parts) if reasoning_parts else "No reasoning provided"

            return actions, full_reasoning

        except Exception as e:
            logger.warning(f"Error parsing structured response: {e}")
            # Fall back to basic action parsing
            return self._parse_actions(response, game_state), "Error parsing reasoning"

    def _process_objectives_from_response(self, objectives_text: str):
        """Process objective management commands from LLM response"""
        try:
            # Look for ADD_OBJECTIVE and COMPLETE_OBJECTIVE commands
            for line in objectives_text.split("\n"):
                line = line.strip()
                if line.upper().startswith("ADD_OBJECTIVE:"):
                    # Parse format: ADD_OBJECTIVE: type:description:target_value
                    content = line[14:].strip()  # Remove "ADD_OBJECTIVE:" prefix
                    parts = content.split(":", 2)  # Split into max 3 parts

                    if len(parts) >= 2:
                        obj_type = parts[0].strip()
                        description = parts[1].strip()
                        target_value = parts[2].strip() if len(parts) > 2 else None

                        # Parse target_value based on type
                        parsed_target = self._parse_target_value(obj_type, target_value)

                        # Add the objective
                        self.add_objective(description, obj_type, parsed_target)

                elif line.upper().startswith("COMPLETE_OBJECTIVE:"):
                    # Parse format: COMPLETE_OBJECTIVE: objective_id:notes
                    content = line[19:].strip()  # Remove "COMPLETE_OBJECTIVE:" prefix
                    parts = content.split(":", 1)  # Split into max 2 parts

                    if len(parts) >= 1:
                        obj_id = parts[0].strip()
                        notes = parts[1].strip() if len(parts) > 1 else "Manually completed by LLM"

                        # Complete the objective
                        success = self.complete_objective(obj_id, notes)
                        if success:
                            logger.info(f"LLM manually completed objective: {obj_id}")
                        else:
                            logger.warning(
                                f"LLM tried to complete non-existent or already completed objective: {obj_id}"
                            )

        except Exception as e:
            logger.warning(f"Error processing objectives from response: {e}")

    def _parse_target_value(self, obj_type: str, target_str: Optional[str]) -> Any:
        """Parse target value based on objective type"""
        if not target_str:
            return None

        try:
            if obj_type == "location":
                # Try to parse coordinates like "(15,20)" or "15,20"
                target_str = target_str.strip("()")
                if "," in target_str:
                    x, y = map(int, target_str.split(","))
                    return (x, y)
            elif obj_type == "map":
                # Try to parse map ID as integer
                return int(target_str)
            else:
                # For other types, return as string
                return target_str
        except (ValueError, TypeError):
            # If parsing fails, return as string
            return target_str

    def get_memory_usage_estimate(self) -> Dict[str, int]:
        """Estimate current memory usage for context management"""
        history_chars = sum(len(str(entry)) for entry in self.state.history)
        recent_actions_chars = sum(len(action) for action in self.state.recent_actions)
        objectives_chars = sum(len(f"{obj.description} {obj.target_value}") for obj in self.state.objectives)

        return {
            "history_entries": len(self.state.history),
            "history_chars": history_chars,
            "recent_actions": len(self.state.recent_actions),
            "recent_actions_chars": recent_actions_chars,
            "objectives_count": len(self.state.objectives),
            "objectives_chars": objectives_chars,
            "estimated_total_chars": history_chars + recent_actions_chars + objectives_chars,
        }

    def get_objectives_state(self) -> Dict[str, Any]:
        """Get objectives formatted for forwarding in game state"""
        return {
            "active": [
                {
                    "id": obj.id,
                    "description": obj.description,
                    "type": obj.objective_type,
                    "target": obj.target_value,
                    "created_at": obj.created_at.isoformat(),
                }
                for obj in self.get_active_objectives()
            ],
            "completed": [
                {
                    "id": obj.id,
                    "description": obj.description,
                    "type": obj.objective_type,
                    "target": obj.target_value,
                    "completed_at": obj.completed_at.isoformat() if obj.completed_at else None,
                    "notes": obj.progress_notes,
                }
                for obj in self.get_completed_objectives()[-5:]  # Last 5 completed
            ],
            "updated": self.state.objectives_updated,
        }

    def trim_history_for_context(self, max_chars: int = 4000):
        """Trim history to fit within context limits"""
        # Preserve minimum history for context
        min_history = max(5, self.history_display_count // 2)
        min_actions = max(10, self.actions_display_count // 2)

        while (
            self.get_memory_usage_estimate()["estimated_total_chars"] > max_chars
            and len(self.state.history) > min_history
        ):
            self.state.history.popleft()

        while (
            len(self.state.recent_actions) > min_actions
            and self.get_memory_usage_estimate()["estimated_total_chars"] > max_chars
        ):
            self.state.recent_actions.popleft()

    def reset_objectives_updated_flag(self):
        """Reset the objectives updated flag (call after forwarding state)"""
        self.state.objectives_updated = False

    def configure_history_limits(
        self,
        max_history_entries: int = None,
        max_recent_actions: int = None,
        history_display_count: int = None,
        actions_display_count: int = None,
        movement_memory_clear_interval: int = None,
    ):
        """Configure history tracking parameters at runtime"""
        if max_history_entries is not None:
            # Create new deque with updated max length, preserving existing data
            existing_history = list(self.state.history)
            self.state.history = deque(existing_history, maxlen=max_history_entries)

        if max_recent_actions is not None:
            # Create new deque with updated max length, preserving existing data
            existing_actions = list(self.state.recent_actions)
            self.state.recent_actions = deque(existing_actions, maxlen=max_recent_actions)

        if history_display_count is not None:
            self.history_display_count = history_display_count

        if actions_display_count is not None:
            self.actions_display_count = actions_display_count

        if movement_memory_clear_interval is not None:
            self.movement_memory_clear_interval = movement_memory_clear_interval

        logger.info(
            f"Updated history configuration: {len(self.state.history)}/{self.state.history.maxlen} history, "
            f"{len(self.state.recent_actions)}/{self.state.recent_actions.maxlen} actions, "
            f"display {self.history_display_count}/{self.actions_display_count}, "
            f"movement memory clear interval: {self.movement_memory_clear_interval}"
        )

    def load_history_from_llm_checkpoint(self, checkpoint_file: str):
        """Load SimpleAgent history from LLM checkpoint file"""
        try:
            import json
            import re
            from datetime import datetime

            from utils.llm_logger import get_llm_logger

            if not os.path.exists(checkpoint_file):
                logger.info(f"No checkpoint file found: {checkpoint_file}")
                return False

            # Use LLM logger to restore cumulative metrics first
            llm_logger = get_llm_logger()
            if llm_logger:
                restored_step_count = llm_logger.load_checkpoint(checkpoint_file)
                if restored_step_count is not None:
                    logger.info(f"✅ LLM logger restored checkpoint with {restored_step_count} steps")
                    # Update SimpleAgent step counter to match LLM logger
                    self.state.step_counter = restored_step_count

            with open(checkpoint_file, "r") as f:
                checkpoint_data = json.load(f)

            log_entries = checkpoint_data.get("log_entries", [])
            restored_count = 0

            for entry in log_entries:
                if entry.get("type") == "interaction" and "simple_mode" in entry.get("interaction_type", ""):
                    try:
                        # Extract state info from prompt
                        prompt = entry.get("prompt", "")
                        response = entry.get("response", "")
                        timestamp_str = entry.get("timestamp", "")

                        # Parse coordinates from prompt
                        coords_match = re.search(r"Position: X=(\d+), Y=(\d+)", prompt)
                        coords = None
                        if coords_match:
                            coords = (int(coords_match.group(1)), int(coords_match.group(2)))

                        # Parse context from prompt
                        context = "overworld"  # default
                        if "Game State: battle" in prompt:
                            context = "battle"
                        elif "DIALOGUE:" in prompt or "dialogue" in prompt.lower():
                            context = "dialogue"
                        elif "menu" in prompt.lower():
                            context = "menu"

                        # Extract action from response
                        action_taken = "UNKNOWN"
                        if "ACTION:" in response:
                            action_section = response.split("ACTION:")[-1].strip()
                            action_line = action_section.split("\n")[0].strip()
                            action_taken = action_line

                        # Parse timestamp
                        timestamp = datetime.now()
                        if timestamp_str:
                            try:
                                timestamp = datetime.fromisoformat(timestamp_str)
                            except:
                                pass

                        # Create simplified game state summary
                        game_state_summary = f"Position: {coords}" if coords else "Position unknown"
                        if coords:
                            game_state_summary += f" | Context: {context}"

                        # Add reasoning summary
                        reasoning = ""
                        if "REASONING:" in response:
                            reasoning_section = response.split("REASONING:")[-1].split("ACTION:")[0].strip()
                            reasoning = reasoning_section

                        action_with_reasoning = (
                            f"{action_taken} | Reasoning: {reasoning}" if reasoning else action_taken
                        )

                        # Create history entry
                        history_entry = HistoryEntry(
                            timestamp=timestamp,
                            player_coords=coords,
                            map_id=None,  # Not available in checkpoint
                            context=context,
                            action_taken=action_with_reasoning,
                            game_state_summary=game_state_summary,
                        )

                        self.state.history.append(history_entry)

                        # Also add to recent actions if it's a valid action
                        if action_taken and action_taken not in ["UNKNOWN", "WAIT"]:
                            # Parse multiple actions if comma-separated
                            actions = [a.strip() for a in action_taken.replace(",", " ").split()]
                            for action in actions:
                                if action in ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT"]:
                                    self.state.recent_actions.append(action)

                        restored_count += 1

                    except Exception as e:
                        logger.warning(f"Error parsing checkpoint entry: {e}")
                        continue

            # Update step counter to match checkpoint
            self.state.step_counter = restored_count

            logger.info(f"✅ Restored {restored_count} history entries from {checkpoint_file}")
            logger.info(f"   History: {len(self.state.history)} entries")
            logger.info(f"   Recent actions: {len(self.state.recent_actions)} actions")
            logger.info(f"   Step counter: {self.state.step_counter}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to load history from checkpoint: {e}")
            import traceback

            traceback.print_exc()
            return False

    def save_history_to_llm_checkpoint(self, checkpoint_file: str = None):
        """Save SimpleAgent history using LLM logger checkpoint system"""
        try:
            from utils.llm_logger import get_llm_logger

            # Get the global LLM logger instance
            llm_logger = get_llm_logger()
            if llm_logger is None:
                logger.warning("No LLM logger available for checkpoint saving")
                return False

            # Save checkpoint using LLM logger which includes cumulative metrics
            # The LLM logger will handle saving log_entries AND cumulative_metrics
            # If checkpoint_file is None, it will use the cache folder
            llm_logger.save_checkpoint(checkpoint_file, agent_step_count=self.state.step_counter)

            logger.info(f"💾 Saved LLM checkpoint to {checkpoint_file}")
            logger.info(f"   Step counter: {self.state.step_counter}")
            logger.info(f"   History: {len(self.state.history)} entries")
            logger.info(f"   Recent actions: {len(self.state.recent_actions)} actions")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save LLM checkpoint: {e}")
            import traceback

            traceback.print_exc()
            return False

    def record_failed_movement(self, coords: Tuple[int, int], direction: str, reason: str = "blocked"):
        """Record a failed movement attempt for future reference"""
        coord_key = f"{coords[0]},{coords[1]}"
        if coord_key not in self.state.failed_movements:
            self.state.failed_movements[coord_key] = []

        failed_entry = f"{direction}:{reason}"
        if failed_entry not in self.state.failed_movements[coord_key]:
            self.state.failed_movements[coord_key].append(failed_entry)
            logger.info(f"Recorded failed movement: {coord_key} -> {direction} ({reason})")

            # Also record in strategic memory for long-term learning (Phase 2.1)
            # Calculate target coords based on direction
            target_coords = coords
            if direction == "UP":
                target_coords = (coords[0], coords[1] - 1)
            elif direction == "DOWN":
                target_coords = (coords[0], coords[1] + 1)
            elif direction == "LEFT":
                target_coords = (coords[0] - 1, coords[1])
            elif direction == "RIGHT":
                target_coords = (coords[0] + 1, coords[1])

            try:
                self.strategic_memory.record_failed_path(coords, target_coords, reason)
            except Exception as e:
                logger.warning(f"Failed to record in strategic memory: {e}")

    def record_npc_interaction(self, coords: Tuple[int, int], interaction_type: str, notes: str = ""):
        """Record an NPC interaction for future reference"""
        coord_key = f"{coords[0]},{coords[1]}"
        interaction_info = f"{interaction_type}: {notes}" if notes else interaction_type
        self.state.npc_interactions[coord_key] = interaction_info
        logger.info(f"Recorded NPC interaction: {coord_key} -> {interaction_info}")

    def get_movement_memory(self, coords: Tuple[int, int]) -> str:
        """Get memory about failed movements and interactions at specific coordinates"""
        coord_key = f"{coords[0]},{coords[1]}"
        memory_parts = []

        # Check for failed movements
        if coord_key in self.state.failed_movements:
            failed_list = self.state.failed_movements[coord_key]
            memory_parts.append(f"Failed moves: {', '.join(failed_list)}")

        # Check for NPC interactions
        if coord_key in self.state.npc_interactions:
            interaction = self.state.npc_interactions[coord_key]
            memory_parts.append(f"NPC: {interaction}")

        return " | ".join(memory_parts) if memory_parts else ""

    def get_area_movement_memory(self, center_coords: Tuple[int, int], radius: int = 7) -> str:
        """Get movement memory for the area around the player"""
        cx, cy = center_coords
        memory_lines = []

        # Check nearby coordinates for failed movements or NPC interactions
        nearby_memories = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue  # Skip current position

                check_coords = (cx + dx, cy + dy)
                memory = self.get_movement_memory(check_coords)
                if memory:
                    nearby_memories.append(f"({check_coords[0]},{check_coords[1]}): {memory}")

        if nearby_memories:
            memory_lines.append("🧠 MOVEMENT MEMORY (nearby area):")
            for memory in nearby_memories[:5]:  # Limit to 5 most relevant
                memory_lines.append(f"  {memory}")

        return "\n".join(memory_lines)

    def clear_movement_memory(self, partial: bool = False):
        """
        Clear movement memory (failed movements and NPC interactions).

        Args:
            partial: If True, only clear old entries (keep recent 5). If False, clear all.
        """
        if partial and (self.state.failed_movements or self.state.npc_interactions):
            # Keep only the 5 most recent entries for each
            if len(self.state.failed_movements) > 5:
                # Convert to list of tuples, sort by insertion order (dict maintains order in Python 3.7+)
                # Keep last 5 entries
                items = list(self.state.failed_movements.items())
                self.state.failed_movements = dict(items[-5:])
                logger.info(
                    f"Partially cleared movement memory, kept {len(self.state.failed_movements)} recent failed movements"
                )

            if len(self.state.npc_interactions) > 5:
                items = list(self.state.npc_interactions.items())
                self.state.npc_interactions = dict(items[-5:])
                logger.info(
                    f"Partially cleared NPC interactions, kept {len(self.state.npc_interactions)} recent interactions"
                )
        else:
            # Clear all movement memory
            cleared_movements = len(self.state.failed_movements)
            cleared_npcs = len(self.state.npc_interactions)
            self.state.failed_movements.clear()
            self.state.npc_interactions.clear()
            logger.info(
                f"Cleared all movement memory: {cleared_movements} failed movements, {cleared_npcs} NPC interactions"
            )

        # Reset the action counter
        self.state.movement_memory_action_counter = 0

    def analyze_movement_preview(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the movement preview data from game state to find valid moves.

        Returns:
            Dict with 'walkable_directions', 'blocked_directions', and 'special_tiles'
        """
        walkable_directions = []
        blocked_directions = []
        special_tiles = {}

        # Look for movement preview in the formatted state
        formatted_state = format_state_for_llm(game_state)
        lines = formatted_state.split("\n")

        in_movement_preview = False
        for line in lines:
            if "MOVEMENT PREVIEW:" in line:
                in_movement_preview = True
                continue

            if in_movement_preview:
                # Parse movement preview lines
                # Format: "  UP   : ( 15, 10) [.] WALKABLE - Optional description"
                if line.strip() and ":" in line:
                    parts = line.strip().split(":")
                    if len(parts) >= 2:
                        direction = parts[0].strip()
                        rest = parts[1].strip()

                        if direction in ["UP", "DOWN", "LEFT", "RIGHT"]:
                            if "WALKABLE" in rest:
                                walkable_directions.append(direction)
                                # Check for special tiles (check stairs before doors to avoid mislabeling)
                                if "Stairs/Warp" in rest:
                                    special_tiles[direction] = "stairs"
                                elif "Door/Entrance" in rest:
                                    special_tiles[direction] = "door"
                                elif "Tall grass" in rest:
                                    special_tiles[direction] = "grass"
                                elif "Jump ledge" in rest and "can jump" in rest:
                                    special_tiles[direction] = "ledge"
                            elif "BLOCKED" in rest:
                                blocked_directions.append(direction)
                elif not line.strip():
                    # Empty line typically ends the movement preview section
                    in_movement_preview = False

        return {
            "walkable_directions": walkable_directions,
            "blocked_directions": blocked_directions,
            "special_tiles": special_tiles,
        }

    def validate_movement_sequence(self, movements: List[str], game_state: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate if a sequence of movements is valid based on current state.

        Args:
            movements: List of movement directions
            game_state: Current game state

        Returns:
            Tuple of (is_valid, reason)
        """
        if not movements:
            return True, "No movements to validate"

        # Special case: During intro/cutscene sequences, movement validation may not work correctly
        # Skip strict validation for known special locations
        try:
            location = game_state.get('player', {}).get('location', '')
            if location in ['MOVING_VAN', 'INTRO']:
                logger.debug(f"Skipping strict movement validation in special location: {location}")
                return True, f"Special location ({location}) - validation relaxed"
        except Exception as e:
            logger.debug(f"Error checking location for validation: {e}")

        # Analyze current movement options
        movement_info = self.analyze_movement_preview(game_state)
        walkable = movement_info["walkable_directions"]
        blocked = movement_info["blocked_directions"]

        # Check first movement
        first_move = movements[0].upper()
        if first_move in blocked:
            return False, f"First movement {first_move} is BLOCKED"

        if first_move not in walkable and first_move in ["UP", "DOWN", "LEFT", "RIGHT"]:
            return False, f"First movement {first_move} is not confirmed WALKABLE"

        # For multiple movements, only allow if we're very confident
        if len(movements) > 1:
            # We can't predict beyond the first move accurately
            # So we should discourage chaining unless explicitly safe
            return False, "Cannot validate multi-step movements - use single steps instead"

        return True, "Movement validated"

    def get_history_stats(self) -> Dict[str, int]:
        """Get current history tracking statistics"""
        return {
            "history_entries": len(self.state.history),
            "max_history_entries": self.state.history.maxlen,
            "recent_actions": len(self.state.recent_actions),
            "max_recent_actions": self.state.recent_actions.maxlen,
            "history_display_count": self.history_display_count,
            "actions_display_count": self.actions_display_count,
            "objectives_count": len(self.state.objectives),
            "step_counter": self.state.step_counter,
            "failed_movements": len(self.state.failed_movements),
            "npc_interactions": len(self.state.npc_interactions),
            "movement_memory_action_counter": self.state.movement_memory_action_counter,
            "movement_memory_clear_interval": self.movement_memory_clear_interval,
        }


# Global simple agent instance for backward compatibility with existing multiprocess code
_global_simple_agent = None


def get_simple_agent(vlm) -> SimpleAgent:
    """Get or create the global simple agent instance"""
    global _global_simple_agent
    if _global_simple_agent is None:
        _global_simple_agent = SimpleAgent(vlm)

        # Check if we should load from checkpoint
        import os

        if os.environ.get("LOAD_CHECKPOINT_MODE") == "true":
            # Check cache folder first, then fall back to old location
            cache_dir = ".pokeagent_cache"
            checkpoint_file = (
                os.path.join(cache_dir, "checkpoint_llm.txt") if os.path.exists(cache_dir) else "checkpoint_llm.txt"
            )
            if not os.path.exists(checkpoint_file) and os.path.exists("checkpoint_llm.txt"):
                checkpoint_file = "checkpoint_llm.txt"
            if os.path.exists(checkpoint_file):
                logger.info(f"🔄 Loading SimpleAgent history from {checkpoint_file}")
                _global_simple_agent.load_history_from_llm_checkpoint(checkpoint_file)
            else:
                logger.info(f"⚠️ No checkpoint file found: {checkpoint_file}")

    elif _global_simple_agent.vlm != vlm:
        # VLM changed, create new instance
        _global_simple_agent = SimpleAgent(vlm)

        # Load checkpoint for new instance too if mode is set
        import os

        if os.environ.get("LOAD_CHECKPOINT_MODE") == "true":
            # Check cache folder first, then fall back to old location
            cache_dir = ".pokeagent_cache"
            checkpoint_file = (
                os.path.join(cache_dir, "checkpoint_llm.txt") if os.path.exists(cache_dir) else "checkpoint_llm.txt"
            )
            if not os.path.exists(checkpoint_file) and os.path.exists("checkpoint_llm.txt"):
                checkpoint_file = "checkpoint_llm.txt"
            if os.path.exists(checkpoint_file):
                logger.info(f"🔄 Loading SimpleAgent history from {checkpoint_file}")
                _global_simple_agent.load_history_from_llm_checkpoint(checkpoint_file)

    return _global_simple_agent


def simple_mode_processing_multiprocess(vlm, game_state, args=None):
    """Simple mode processing function for multiprocess mode (backward compatibility)"""
    # args parameter kept for backward compatibility but not used
    _ = args  # Acknowledge unused parameter
    agent = get_simple_agent(vlm)
    frame = game_state["visual"]["screenshot"]

    # CRITICAL: Validate frame before processing
    if frame is None:
        logger.error("🚫 CRITICAL: simple_step called with None frame")
        return "WAIT"

    return agent.process_step(frame, game_state)
