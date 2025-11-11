#!/usr/bin/env python3
"""
Frontier Detection System for Systematic Exploration

Implements frontier-based exploration inspired by poke.AI's approach.
Frontiers are unvisited tiles at the boundary between explored and unexplored regions.

Based on frontier-based exploration algorithms from robotics:
- Identifies boundary points using BFS
- Scores frontiers based on surrounding tile types
- Prioritizes high-value exploration targets (gyms, houses, NPCs)
"""

import logging
import random
from collections import deque
from typing import Dict, List, Set, Tuple, Optional, Any
import heapq

from pokemon_env.enums import MetatileBehavior
from utils.map_formatter import format_tile_to_symbol

logger = logging.getLogger(__name__)


class FrontierDetector:
    """
    Detects and scores frontier points for systematic exploration.

    Frontiers are unvisited tiles at the boundary between explored
    and unexplored regions. This implementation adapts poke.AI's
    frontier-based exploration to work with the current VLM-based agent.
    """

    # Tile type scoring based on poke.AI weights, adapted for our symbols
    TILE_SCORES = {
        # Unexplored/exploration potential
        'unexplored': 20,
        '.': 0,  # Visited walkable

        # High-value locations (story progression)
        'G': 100,   # Gym (highest priority)
        'C': 55,    # Pokecenter (healing)
        'M': 40,    # Pokemart (items)
        'H': 70,    # House (NPCs, story)
        'N': 65,    # NPC (trainers, dialogue)

        # Medium-value locations
        '~': 15,    # Tall grass (wild Pokemon)
        'S': 50,    # Stairs (new areas)
        'D': 50,    # Doors (new areas)

        # Low-value/obstacles
        'W': -10,   # Water (usually blocked)
        '#': -40,   # Wall/obstacle
        '?': 10,    # Unexplored edge (questionable)

        # Directional (ledges - one-way)
        '↑': 5, '↓': 5, '←': 5, '→': 5,
        '↗': 5, '↘': 5, '↙': 5, '↖': 5,
    }

    def __init__(
        self,
        max_search_depth: int = 50,
        max_frontiers_returned: int = 20,
        distance_penalty_factor: float = 0.5,
        enable_randomization: bool = True
    ):
        """
        Initialize frontier detector.

        Args:
            max_search_depth: Maximum BFS depth to search (prevents infinite loops)
            max_frontiers_returned: Maximum number of frontiers to return
            distance_penalty_factor: Penalty per unit distance from player
            enable_randomization: Add randomness to frontier selection
        """
        self.max_search_depth = max_search_depth
        self.max_frontiers_returned = max_frontiers_returned
        self.distance_penalty_factor = distance_penalty_factor
        self.enable_randomization = enable_randomization

        self.visited_bfs = set()  # Tracks visited tiles during BFS
        self.cache = {}  # Cache for performance optimization

    def detect_frontiers(
        self,
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int],
        unreachable: Optional[Set[Tuple[int, int]]] = None,
        current_objective: Optional[Tuple[int, int]] = None
    ) -> List[Tuple[float, int, int]]:
        """
        Detect frontier points using BFS from center of explored region.

        This is the main entry point. It performs a breadth-first search
        to identify all unvisited tiles at the boundary of explored areas,
        scores them, and returns the top candidates.

        Args:
            game_state: Current game state with map data
            player_pos: Player's current (x, y) position
            unreachable: Set of (x, y) positions marked as unreachable
            current_objective: Optional (x, y) of current objective for bonus scoring

        Returns:
            List of (score, x, y) tuples sorted by score (descending)
        """
        unreachable = unreachable or set()

        # Extract map data
        map_data = game_state.get('map', {})
        if not map_data:
            logger.warning("No map data available for frontier detection")
            return []

        # Find a good starting point for BFS (prefer center of explored area)
        start_pos = self._find_exploration_start(game_state, player_pos)
        if not start_pos:
            logger.warning("Could not find starting point for frontier detection")
            return []

        # Perform BFS to find all frontiers
        frontiers = self._run_frontier_bfs(
            start_pos=start_pos,
            game_state=game_state,
            player_pos=player_pos,
            unreachable=unreachable,
            current_objective=current_objective
        )

        # Sort by score (highest first) and return top N
        frontiers.sort(key=lambda x: -x[0])  # Sort by score descending
        top_frontiers = frontiers[:self.max_frontiers_returned]

        logger.info(f"Detected {len(frontiers)} frontiers, returning top {len(top_frontiers)}")
        return top_frontiers

    def _find_exploration_start(
        self,
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Find a good starting point for BFS exploration.

        Strategy:
        1. Try random explored tiles near player
        2. Fall back to player position
        3. Prioritize tiles that are walkable and not at edges

        Args:
            game_state: Current game state
            player_pos: Player position (x, y)

        Returns:
            (x, y) starting position for BFS
        """
        map_data = game_state.get('map', {})

        # Try random tiles near player (within 10 tile radius)
        attempts = 20 if self.enable_randomization else 1
        for _ in range(attempts):
            if self.enable_randomization:
                dx = random.randint(-10, 10)
                dy = random.randint(-10, 10)
            else:
                dx, dy = 0, 0

            x, y = player_pos[0] + dx, player_pos[1] + dy

            # Check if this tile is explored and walkable
            if self._is_tile_explored(x, y, game_state):
                return (x, y)

        # Fallback to player position
        return player_pos

    def _run_frontier_bfs(
        self,
        start_pos: Tuple[int, int],
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int],
        unreachable: Set[Tuple[int, int]],
        current_objective: Optional[Tuple[int, int]]
    ) -> List[Tuple[float, int, int]]:
        """
        Run BFS to find all frontier points and score them.

        Args:
            start_pos: Starting position for BFS
            game_state: Current game state
            player_pos: Player position
            unreachable: Set of unreachable positions
            current_objective: Current objective position (optional)

        Returns:
            List of (score, x, y) tuples
        """
        frontiers = []
        self.visited_bfs = set()
        queue = deque([start_pos])
        self.visited_bfs.add(start_pos)
        depth = 0

        while queue and depth < self.max_search_depth:
            level_size = len(queue)

            for _ in range(level_size):
                x, y = queue.popleft()

                # Check if this position is a frontier
                if self._is_frontier(x, y, game_state):
                    if (x, y) not in unreachable:
                        score = self._score_frontier(
                            x, y, game_state, player_pos, current_objective
                        )
                        frontiers.append((score, x, y))

                # Add unvisited walkable neighbors to queue (4-directional)
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = x + dx, y + dy

                    if (nx, ny) not in self.visited_bfs:
                        # Add to queue if it's a valid tile to explore from
                        if self._is_tile_explorable(nx, ny, game_state):
                            self.visited_bfs.add((nx, ny))
                            queue.append((nx, ny))

            depth += 1

        logger.debug(f"BFS completed at depth {depth}, found {len(frontiers)} frontiers")
        return frontiers

    def _is_frontier(
        self,
        x: int,
        y: int,
        game_state: Dict[str, Any]
    ) -> bool:
        """
        Check if a position is a frontier point.

        A frontier is an unvisited tile that has at least one visited neighbor.
        This represents the boundary between explored and unexplored regions.

        Args:
            x: X coordinate
            y: Y coordinate
            game_state: Current game state

        Returns:
            True if position is a frontier
        """
        # Must be unexplored
        if not self._is_tile_unexplored(x, y, game_state):
            return False

        # Must have at least one explored neighbor (4-directional)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if self._is_tile_explored(nx, ny, game_state):
                return True

        return False

    def _score_frontier(
        self,
        x: int,
        y: int,
        game_state: Dict[str, Any],
        player_pos: Tuple[int, int],
        current_objective: Optional[Tuple[int, int]]
    ) -> float:
        """
        Score a frontier based on surrounding tiles and other factors.

        Scoring factors:
        1. Surrounding tile types (8-directional)
        2. Distance from player (penalty)
        3. Alignment with current objective (bonus)
        4. Random factor for exploration diversity

        Args:
            x: Frontier X coordinate
            y: Frontier Y coordinate
            game_state: Current game state
            player_pos: Player position
            current_objective: Current objective position (optional)

        Returns:
            Float score (higher is better)
        """
        score = 0.0

        # 1. Base score from surrounding tiles (8-directional)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue

                neighbor_score = self._get_tile_score(x + dx, y + dy, game_state)
                score += neighbor_score

        # 2. Distance penalty (prefer closer frontiers)
        distance = abs(x - player_pos[0]) + abs(y - player_pos[1])
        score -= distance * self.distance_penalty_factor

        # 3. Objective alignment bonus
        if current_objective:
            # Calculate if frontier is in the general direction of objective
            obj_x, obj_y = current_objective

            # Direction vectors
            to_frontier_x = x - player_pos[0]
            to_frontier_y = y - player_pos[1]
            to_objective_x = obj_x - player_pos[0]
            to_objective_y = obj_y - player_pos[1]

            # Dot product to measure alignment
            dot_product = (to_frontier_x * to_objective_x +
                          to_frontier_y * to_objective_y)

            if dot_product > 0:  # Same general direction
                score += 30  # Bonus for objective alignment

        # 4. Small random factor for diversity (if enabled)
        if self.enable_randomization:
            score += random.uniform(-2, 2)

        return score

    def _get_tile_score(
        self,
        x: int,
        y: int,
        game_state: Dict[str, Any]
    ) -> float:
        """
        Get the score for a specific tile based on its type.

        Args:
            x: X coordinate
            y: Y coordinate
            game_state: Current game state

        Returns:
            Float score for this tile type
        """
        # Get tile symbol
        symbol = self._get_tile_symbol(x, y, game_state)

        # Return score from lookup table
        return self.TILE_SCORES.get(symbol, 0)

    def _get_tile_symbol(
        self,
        x: int,
        y: int,
        game_state: Dict[str, Any]
    ) -> str:
        """
        Get the symbol representing a tile at position (x, y).

        This integrates with the existing map formatter to get consistent symbols.

        Args:
            x: X coordinate
            y: Y coordinate
            game_state: Current game state

        Returns:
            String symbol ('.', '#', 'G', 'C', etc.)
        """
        map_data = game_state.get('map', {})
        raw_tiles = map_data.get('tiles', [])

        if not raw_tiles:
            return '#'  # Unknown = wall

        # Get player position to calculate relative tile position
        player_x = game_state.get('player', {}).get('x', 0)
        player_y = game_state.get('player', {}).get('y', 0)

        # Memory tiles are 15x15 centered on player
        radius = 7
        rel_x = x - player_x + radius
        rel_y = y - player_y + radius

        # Check bounds
        if rel_y < 0 or rel_y >= len(raw_tiles):
            return '?'  # Out of bounds = unexplored
        if rel_x < 0 or rel_x >= len(raw_tiles[rel_y]):
            return '?'  # Out of bounds = unexplored

        tile_data = raw_tiles[rel_y][rel_x]

        if not tile_data or len(tile_data) < 2:
            return '?'  # No data = unexplored

        # Use existing formatter to get symbol
        location_name = game_state.get('player', {}).get('location')
        symbol = format_tile_to_symbol(
            tile_data,
            x=x,
            y=y,
            location_name=location_name
        )

        return symbol

    def _is_tile_unexplored(
        self,
        x: int,
        y: int,
        game_state: Dict[str, Any]
    ) -> bool:
        """
        Check if a tile is unexplored (outside visible range or unknown).

        Args:
            x: X coordinate
            y: Y coordinate
            game_state: Current game state

        Returns:
            True if tile is unexplored
        """
        symbol = self._get_tile_symbol(x, y, game_state)
        return symbol == '?'

    def _is_tile_explored(
        self,
        x: int,
        y: int,
        game_state: Dict[str, Any]
    ) -> bool:
        """
        Check if a tile has been explored (is in visible range).

        Args:
            x: X coordinate
            y: Y coordinate
            game_state: Current game state

        Returns:
            True if tile is explored
        """
        symbol = self._get_tile_symbol(x, y, game_state)
        return symbol != '?'

    def _is_tile_explorable(
        self,
        x: int,
        y: int,
        game_state: Dict[str, Any]
    ) -> bool:
        """
        Check if a tile can be used for exploration (walkable and explored).

        Args:
            x: X coordinate
            y: Y coordinate
            game_state: Current game state

        Returns:
            True if tile is explorable (can BFS from it)
        """
        symbol = self._get_tile_symbol(x, y, game_state)

        # Can explore from: walkable tiles, doors, stairs
        # Cannot explore from: walls, water, unexplored
        explorable_symbols = ['.', 'S', 'D', '~', 'P']
        return symbol in explorable_symbols

    def format_frontiers_for_prompt(
        self,
        frontiers: List[Tuple[float, int, int]],
        max_display: int = 5
    ) -> str:
        """
        Format frontier list for inclusion in VLM prompt.

        Args:
            frontiers: List of (score, x, y) tuples
            max_display: Maximum number of frontiers to display

        Returns:
            Formatted string for prompt
        """
        if not frontiers:
            return ""

        lines = ["**EXPLORATION TARGETS** (frontier-based navigation):"]

        for i, (score, x, y) in enumerate(frontiers[:max_display], 1):
            lines.append(f"  {i}. Frontier at ({x}, {y}) - Score: {score:.1f}")

        lines.append("")
        lines.append("To auto-navigate to a frontier, respond with: FRONTIER_N (e.g., FRONTIER_1)")

        return "\n".join(lines)


def create_frontier_detector(config: Optional[Dict[str, Any]] = None) -> FrontierDetector:
    """
    Factory function to create a FrontierDetector with configuration.

    Args:
        config: Optional configuration dictionary with keys:
            - max_search_depth: int (default 50)
            - max_frontiers_returned: int (default 20)
            - distance_penalty_factor: float (default 0.5)
            - enable_randomization: bool (default True)

    Returns:
        Configured FrontierDetector instance
    """
    config = config or {}

    return FrontierDetector(
        max_search_depth=config.get('max_search_depth', 50),
        max_frontiers_returned=config.get('max_frontiers_returned', 20),
        distance_penalty_factor=config.get('distance_penalty_factor', 0.5),
        enable_randomization=config.get('enable_randomization', True)
    )
