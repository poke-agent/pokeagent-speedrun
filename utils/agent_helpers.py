"""
Shared helper functions for all agents.
"""

import logging
import os
import re
import json
import requests
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from utils.llm_logger import get_llm_logger

logger = logging.getLogger(__name__)


def update_server_metrics(server_url: str = "http://localhost:8000") -> None:
    """
    Update server with current agent step count and LLM metrics.

    This is a shared function used by all agents to send metrics to the server
    for display in the web interface.

    Args:
        server_url: Base URL of the server (default: http://localhost:8000)
    """
    try:

        # Get current LLM metrics
        llm_logger = get_llm_logger()
        metrics = llm_logger.get_cumulative_metrics()

        # Send metrics to server
        try:
            response = requests.post(
                f"{server_url}/agent_step",
                json={"metrics": metrics},
                timeout=1
            )
            if response.status_code != 200:
                logger.debug(f"Failed to update server metrics: {response.status_code}")
        except requests.exceptions.RequestException:
            # Silent fail - server might not be running or in different mode
            pass

    except Exception as e:
        logger.debug(f"Error updating server metrics: {e}")


def initialize_storyline_objectives(objectives_list: List[Any]) -> List[Dict[str, Any]]:
    """
    Initialize the main storyline objectives for Pokémon Emerald progression.

    Args:
        objectives_list: List to append Objective instances to

    Returns:
        List of dictionaries with objective data that can be used to create Objective instances
    """
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
            "description": "Set the clock on the wall in the player's bedroom. Interact with the clock at (5,1) by pressing A while facing it, select YES, talk to Mom. Then, leave the house.",
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

    logger.info(
        f"Initialized {len(storyline_objectives)} storyline objectives for Emerald progression (up to first gym)"
    )

    return storyline_objectives


def load_history_from_llm_checkpoint(
    checkpoint_file: str, agent_state: Any, history_entry_class: Any, step_counter_attr: str = "step_counter"
) -> bool:
    """
    Load SimpleAgent history from LLM checkpoint file.

    Args:
        checkpoint_file: Path to checkpoint JSON file
        agent_state: Agent state object to populate (should have history, recent_actions, step_counter)
        history_entry_class: HistoryEntry dataclass for creating history entries
        step_counter_attr: Name of the step counter attribute (default: "step_counter")

    Returns:
        True if successful, False otherwise
    """
    try:
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
                setattr(agent_state, step_counter_attr, restored_step_count)

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
                    history_entry = history_entry_class(
                        timestamp=timestamp,
                        player_coords=coords,
                        map_id=None,  # Not available in checkpoint
                        context=context,
                        action_taken=action_with_reasoning,
                        game_state_summary=game_state_summary,
                    )

                    agent_state.history.append(history_entry)

                    # Also add to recent actions if it's a valid action
                    if action_taken and action_taken not in ["UNKNOWN", "WAIT"]:
                        # Parse multiple actions if comma-separated
                        actions = [a.strip() for a in action_taken.replace(",", " ").split()]
                        for action in actions:
                            if action in ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT"]:
                                agent_state.recent_actions.append(action)

                    restored_count += 1

                except Exception as e:
                    logger.warning(f"Error parsing checkpoint entry: {e}")
                    continue

        # Update step counter to match checkpoint
        setattr(agent_state, step_counter_attr, restored_count)

        logger.info(f"✅ Restored {restored_count} history entries from {checkpoint_file}")
        logger.info(f"   History: {len(agent_state.history)} entries")
        logger.info(f"   Recent actions: {len(agent_state.recent_actions)} actions")
        logger.info(f"   Step counter: {getattr(agent_state, step_counter_attr)}")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to load history from checkpoint: {e}")
        import traceback

        traceback.print_exc()
        return False


def save_history_to_llm_checkpoint(checkpoint_file: Optional[str], agent_step_count: int) -> bool:
    """
    Save SimpleAgent history using LLM logger checkpoint system.

    Args:
        checkpoint_file: Path to save checkpoint (None = use cache folder)
        agent_step_count: Current agent step counter value

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get the global LLM logger instance
        llm_logger = get_llm_logger()
        if llm_logger is None:
            logger.warning("No LLM logger available for checkpoint saving")
            return False

        # Save checkpoint using LLM logger which includes cumulative metrics
        # The LLM logger will handle saving log_entries AND cumulative_metrics
        # If checkpoint_file is None, it will use the cache folder
        llm_logger.save_checkpoint(checkpoint_file, agent_step_count=agent_step_count)

        logger.info(f"💾 Saved LLM checkpoint to {checkpoint_file}")
        logger.info(f"   Step counter: {agent_step_count}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to save LLM checkpoint: {e}")
        import traceback

        traceback.print_exc()
        return False


def analyze_movement_preview(game_state: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Analyze the movement preview data from game state to find valid moves.

    Args:
        game_state: Current game state dictionary

    Returns:
        Dict with 'walkable_directions', 'blocked_directions', and 'special_tiles'
    """
    from utils.state_formatter import format_state_for_llm

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


def validate_movement_sequence(movements: List[str], game_state: Dict[str, Any]) -> Tuple[bool, str]:
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
        location = game_state.get("player", {}).get("location", "")
        if location in ["MOVING_VAN", "INTRO"]:
            logger.debug(f"Skipping strict movement validation in special location: {location}")
            return True, f"Special location ({location}) - validation relaxed"
    except Exception as e:
        logger.debug(f"Error checking location for validation: {e}")

    # Analyze current movement options
    movement_info = analyze_movement_preview(game_state)
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


def format_dynamic_objectives_for_prompt(active_objectives: List[Any], completed_objectives_ids: set = None) -> str:
    """
    Format only the currently active/relevant objectives for the system prompt.
    Shows current objective + next 2-3 upcoming objectives for context.

    Args:
        active_objectives: List of active Objective instances from agent state
        completed_objectives_ids: Set of completed objective IDs

    Returns:
        Formatted string with current and next objectives
    """
    if completed_objectives_ids is None:
        completed_objectives_ids = set()

    all_objectives = initialize_storyline_objectives([])
    obj_map = {obj["id"]: obj for obj in all_objectives}

    # Find first incomplete objective
    current_obj_idx = None
    for i, obj_data in enumerate(all_objectives):
        if obj_data["id"] not in completed_objectives_ids:
            current_obj_idx = i
            break

    if current_obj_idx is None:
        return "✅ All storyline objectives completed! Continue exploring or challenge the Elite Four."

    # Show current + next 3 objectives for context
    relevant_objectives = all_objectives[current_obj_idx:min(current_obj_idx + 4, len(all_objectives))]

    formatted_lines = [
        "🎯 CURRENT OBJECTIVE & NEXT STEPS:",
        ""
    ]

    for i, obj_data in enumerate(relevant_objectives):
        obj = obj_map[obj_data["id"]]
        status = "➡️ **CURRENT**" if i == 0 else f"   Next {i}"

        formatted_lines.append(f"{status}: {obj['description']}")

        # Add special instructions for current objective
        if i == 0:
            if obj.get("target_coords"):
                formatted_lines.append(f"     📍 Navigate to: {obj['target_coords']}")
            if obj.get("target_floor"):
                formatted_lines.append(f"     🪜 Floor: {obj['target_floor']}")
            if obj.get("target_object"):
                formatted_lines.append(f"     🔍 Look for: {obj['target_object']}")

    formatted_lines.extend([
        "",
        "⚡ FOCUS:",
        "- Complete the CURRENT objective before moving to next steps",
        "- Next objectives are shown for planning ahead only",
        "- Every action should help complete the current objective"
    ])

    return "\n".join(formatted_lines)
