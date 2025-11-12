"""
Intelligent Collision Handling System - Phase 5.1

Implements sophisticated collision tracking, recovery, and path re-planning
based on reference implementation from poke.AI-master/ai/path_finder.py.

Key Features:
- Consecutive collision tracking with configurable limits
- Consecutive movement tracking for collision counter reset
- Unreachable position tracking to avoid repeating failed attempts
- Dynamic recovery strategies based on collision patterns
- Integration with existing strategic memory system

Competition Compliance:
- Uses only standard game state information
- No additional memory reading
- Button inputs only
- Fully deterministic and reproducible
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Optional, List, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class CollisionState:
    """Track collision state at a specific location"""

    position: Tuple[int, int]
    collision_count: int = 0
    last_attempted_action: Optional[str] = None
    failed_actions: Set[str] = field(default_factory=set)
    timestamp: int = 0


class CollisionHandler:
    """
    Intelligent collision tracking and recovery system.

    Tracks consecutive collisions, successful movements, and unreachable positions
    to prevent the agent from getting stuck in navigation loops.
    """

    def __init__(
        self,
        consecutive_collision_limit: int = 5,
        consecutive_movement_reset_threshold: int = 2,
        cache_dir: str = ".pokeagent_cache",
    ):
        """
        Initialize collision handler.

        Args:
            consecutive_collision_limit: Number of consecutive collisions before
                marking position as unreachable (default: 5, from reference)
            consecutive_movement_reset_threshold: Number of successful movements
                needed to reset collision counter (default: 2)
            cache_dir: Directory for persistent collision data
        """
        self.consecutive_collision_limit = consecutive_collision_limit
        self.consecutive_movement_reset_threshold = consecutive_movement_reset_threshold
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Tracking state
        self.consecutive_collisions = 0
        self.consecutive_movements = 0
        self.last_position: Optional[Tuple[int, int]] = None
        self.last_action: Optional[str] = None

        # Unreachable positions (persistent across session)
        self.unreachable_positions: Set[Tuple[int, int, str]] = set()

        # Collision state per position
        self.collision_states: Dict[Tuple[int, int], CollisionState] = {}

        # Statistics
        self.total_collisions = 0
        self.total_recoveries = 0
        self.total_abandoned_positions = 0

        # Load persistent data
        self._load_unreachable_positions()

        logger.info(
            f"CollisionHandler initialized (collision_limit={consecutive_collision_limit}, "
            f"movement_reset={consecutive_movement_reset_threshold})"
        )

    def _load_unreachable_positions(self):
        """Load unreachable positions from cache"""
        cache_file = self.cache_dir / "unreachable_positions.json"
        try:
            if cache_file.exists():
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    # Convert list of lists back to set of tuples
                    self.unreachable_positions = {
                        tuple(pos) for pos in data.get("unreachable_positions", [])
                    }
                logger.info(
                    f"Loaded {len(self.unreachable_positions)} unreachable positions from cache"
                )
        except Exception as e:
            logger.warning(f"Failed to load unreachable positions: {e}")

    def _save_unreachable_positions(self):
        """Save unreachable positions to cache"""
        cache_file = self.cache_dir / "unreachable_positions.json"
        try:
            data = {
                "unreachable_positions": [list(pos) for pos in self.unreachable_positions],
                "total_abandoned": self.total_abandoned_positions,
            }
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save unreachable positions: {e}")

    def record_movement(
        self, current_position: Tuple[int, int], action: str, moved: bool
    ) -> Dict[str, Any]:
        """
        Record a movement attempt and determine collision status.

        Args:
            current_position: Current (x, y) coordinates
            action: Action attempted (UP, DOWN, LEFT, RIGHT)
            moved: Whether position changed after action

        Returns:
            Dict with collision status and recommended actions
        """
        result = {
            "collision_detected": False,
            "consecutive_collisions": self.consecutive_collisions,
            "consecutive_movements": self.consecutive_movements,
            "should_abandon": False,
            "is_unreachable": False,
            "recovery_suggestion": None,
        }

        # Check if this position is already marked unreachable
        pos_key = (current_position[0], current_position[1], action)
        if pos_key in self.unreachable_positions:
            result["is_unreachable"] = True
            result["recovery_suggestion"] = "AVOID_POSITION"
            logger.warning(
                f"⚠️ Position {current_position} with action {action} is marked unreachable"
            )
            return result

        # Determine if collision occurred
        # Collision = attempted directional movement but position didn't change
        collision = False
        if action in ["UP", "DOWN", "LEFT", "RIGHT"]:
            if not moved:
                # Tried to move but stayed in place = collision
                collision = True

        if collision:
            # Collision detected
            self.consecutive_collisions += 1
            self.consecutive_movements = 0  # Reset movement counter
            self.total_collisions += 1

            result["collision_detected"] = True
            result["consecutive_collisions"] = self.consecutive_collisions

            # Update collision state for this position
            if current_position not in self.collision_states:
                self.collision_states[current_position] = CollisionState(
                    position=current_position
                )

            state = self.collision_states[current_position]
            state.collision_count += 1
            state.last_attempted_action = action
            state.failed_actions.add(action)

            logger.warning(
                f"🚧 Collision detected at {current_position} "
                f"(consecutive: {self.consecutive_collisions}/{self.consecutive_collision_limit}, "
                f"action: {action})"
            )

            # Check if we should abandon this position
            if self.consecutive_collisions >= self.consecutive_collision_limit:
                self._mark_unreachable(current_position, action)
                result["should_abandon"] = True
                result["recovery_suggestion"] = "ABANDON_PATH"
                logger.error(
                    f"❌ Too many consecutive collisions ({self.consecutive_collisions})! "
                    f"Marking {current_position} as unreachable."
                )
            else:
                # Suggest recovery based on failed actions
                result["recovery_suggestion"] = self._suggest_recovery(
                    current_position, action
                )

        else:
            # Successful movement or non-movement action
            if moved and action in ["UP", "DOWN", "LEFT", "RIGHT"]:
                self.consecutive_movements += 1

                # Reset collision counter if enough successful movements
                if (
                    self.consecutive_movements
                    >= self.consecutive_movement_reset_threshold
                ):
                    if self.consecutive_collisions > 0:
                        logger.info(
                            f"✅ Collision counter reset after {self.consecutive_movements} successful movements"
                        )
                        self.total_recoveries += 1
                    self.consecutive_collisions = 0

        # Update last position and action
        self.last_position = current_position
        self.last_action = action

        result["consecutive_collisions"] = self.consecutive_collisions
        result["consecutive_movements"] = self.consecutive_movements

        return result

    def _mark_unreachable(self, position: Tuple[int, int], action: str):
        """Mark a position + action combination as unreachable"""
        pos_key = (position[0], position[1], action)
        self.unreachable_positions.add(pos_key)
        self.total_abandoned_positions += 1

        # Reset consecutive collision counter
        self.consecutive_collisions = 0

        # Save to persistent cache
        self._save_unreachable_positions()

        logger.error(
            f"❌ Marked position {position} with action {action} as unreachable "
            f"(total unreachable: {len(self.unreachable_positions)})"
        )

    def _suggest_recovery(
        self, position: Tuple[int, int], failed_action: str
    ) -> str:
        """
        Suggest a recovery action based on collision pattern.

        Args:
            position: Current position where collision occurred
            failed_action: The action that resulted in collision

        Returns:
            Recovery suggestion string
        """
        if position not in self.collision_states:
            return "TRY_ALTERNATE"

        state = self.collision_states[position]

        # If all 4 directions failed, suggest abandoning
        if len(state.failed_actions) >= 4:
            return "ABANDON_PATH"

        # Suggest trying directions that haven't failed yet
        all_directions = {"UP", "DOWN", "LEFT", "RIGHT"}
        untried = all_directions - state.failed_actions

        if untried:
            return f"TRY_ALTERNATE: {', '.join(sorted(untried))}"

        return "TRY_ALTERNATE"

    def is_position_unreachable(
        self, position: Tuple[int, int], action: Optional[str] = None
    ) -> bool:
        """
        Check if a position (and optionally action) is marked as unreachable.

        Args:
            position: Position to check
            action: Optional specific action to check

        Returns:
            True if unreachable, False otherwise
        """
        if action:
            return (position[0], position[1], action) in self.unreachable_positions

        # Check if any action at this position is unreachable
        for direction in ["UP", "DOWN", "LEFT", "RIGHT"]:
            if (position[0], position[1], direction) in self.unreachable_positions:
                return True

        return False

    def get_safe_directions(
        self, position: Tuple[int, int]
    ) -> List[str]:
        """
        Get list of directions that are NOT marked as unreachable.

        Args:
            position: Current position

        Returns:
            List of safe direction strings
        """
        all_directions = ["UP", "DOWN", "LEFT", "RIGHT"]
        safe = [
            direction
            for direction in all_directions
            if (position[0], position[1], direction) not in self.unreachable_positions
        ]
        return safe

    def get_collision_warning(self, position: Tuple[int, int]) -> Optional[str]:
        """
        Get a warning message if position has collision history.

        Args:
            position: Position to check

        Returns:
            Warning string or None
        """
        if position not in self.collision_states:
            return None

        state = self.collision_states[position]
        if state.collision_count == 0:
            return None

        failed_str = ", ".join(sorted(state.failed_actions))
        return (
            f"⚠️ COLLISION HISTORY at {position}: "
            f"{state.collision_count} collisions, failed actions: {failed_str}"
        )

    def format_status(self) -> str:
        """Format current collision handler status for display"""
        lines = [
            "COLLISION HANDLER STATUS",
            "=" * 50,
            f"Consecutive Collisions: {self.consecutive_collisions}/{self.consecutive_collision_limit}",
            f"Consecutive Movements: {self.consecutive_movements}",
            f"Unreachable Positions: {len(self.unreachable_positions)}",
            f"Total Collisions: {self.total_collisions}",
            f"Total Recoveries: {self.total_recoveries}",
            f"Total Abandoned: {self.total_abandoned_positions}",
        ]

        # Show recent unreachable positions (last 5)
        if self.unreachable_positions:
            lines.append("\nRecent Unreachable Positions:")
            recent = list(self.unreachable_positions)[-5:]
            for pos in recent:
                lines.append(f"  • {pos}")

        return "\n".join(lines)

    def get_statistics(self) -> Dict[str, Any]:
        """Get collision handler statistics for metrics"""
        return {
            "consecutive_collisions": self.consecutive_collisions,
            "consecutive_movements": self.consecutive_movements,
            "total_collisions": self.total_collisions,
            "total_recoveries": self.total_recoveries,
            "total_abandoned": self.total_abandoned_positions,
            "unreachable_positions_count": len(self.unreachable_positions),
            "collision_states_count": len(self.collision_states),
        }

    def reset_session(self):
        """Reset session-specific data (but keep persistent unreachable positions)"""
        self.consecutive_collisions = 0
        self.consecutive_movements = 0
        self.last_position = None
        self.last_action = None
        self.collision_states.clear()
        logger.info("Collision handler session reset")

    def clear_unreachable_positions(self):
        """Clear all unreachable positions (useful for testing or new game)"""
        self.unreachable_positions.clear()
        self.total_abandoned_positions = 0
        self._save_unreachable_positions()
        logger.info("Cleared all unreachable positions")


# Singleton instance
_collision_handler_instance: Optional[CollisionHandler] = None


def get_collision_handler(reset: bool = False) -> CollisionHandler:
    """
    Get or create the global collision handler instance.

    Args:
        reset: If True, create a new instance

    Returns:
        CollisionHandler instance
    """
    global _collision_handler_instance

    if reset or _collision_handler_instance is None:
        _collision_handler_instance = CollisionHandler()

    return _collision_handler_instance
