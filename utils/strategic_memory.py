"""
Strategic Memory System for Pokemon Emerald Agent

Phase 2.1 implementation from TRACK2_SIMPLE_AGENT_OPTIMIZATION_PLAN.md

Provides long-term memory for:
- Battle outcomes (learn from victories/defeats)
- Failed paths (avoid blocked routes)
- NPC interactions (track dialogue results)
- Item locations (remember useful items)
- Warp connections (understand map transitions)
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

logger = logging.getLogger(__name__)


@dataclass
class BattleMemory:
    """Record of a battle outcome"""
    trainer_name: str
    location: str
    outcome: str  # "win", "loss", "fled"
    player_team: List[str]  # Pokemon species used
    opponent_team: List[str]  # Pokemon species faced
    turns: int  # Number of turns
    timestamp: str
    notes: str = ""


@dataclass
class PathMemory:
    """Record of a failed navigation path"""
    start_coords: Tuple[int, int]
    end_coords: Tuple[int, int]
    reason: str  # "blocked", "npc_collision", "ledge", "water", etc.
    attempts: int  # How many times this path was tried
    timestamp: str


@dataclass
class NPCMemory:
    """Record of NPC interaction"""
    npc_id: str  # Unique identifier (coords + location)
    location: str
    coords: Tuple[int, int]
    interaction_type: str  # "dialogue", "battle", "item", "trade"
    result: str  # What happened
    dialogue_length: int  # Number of text boxes
    timestamp: str
    important: bool = False  # Required for progression


@dataclass
class ItemMemory:
    """Record of item location"""
    item_name: str
    location: str
    coords: Tuple[int, int]
    obtained: bool
    timestamp: str


@dataclass
class WarpMemory:
    """Record of warp/portal connection"""
    from_location: str
    from_coords: Tuple[int, int]
    to_location: str
    to_coords: Tuple[int, int]
    warp_type: str  # "door", "stairs", "portal", "cave_entrance"
    timestamp: str


class StrategicMemory:
    """
    Long-term memory system for strategic decision making.

    Persists important information across runs to avoid repeating mistakes
    and leverage learned knowledge.
    """

    def __init__(self, cache_dir: str = ".pokeagent_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Memory stores
        self.battle_outcomes: Dict[str, BattleMemory] = {}
        self.failed_paths: Set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()
        self.path_attempts: Dict[str, int] = defaultdict(int)  # path_key -> attempt_count
        self.npc_interactions: Dict[str, NPCMemory] = {}
        self.item_locations: Dict[str, ItemMemory] = {}
        self.warp_connections: Dict[str, WarpMemory] = {}

        # Statistics
        self.total_battles = 0
        self.battles_won = 0
        self.battles_lost = 0
        self.paths_blocked = 0
        self.npcs_encountered = 0

        # Load from cache if exists
        self._load_from_cache()

        logger.info(f"Strategic Memory initialized: {self.total_battles} battles, "
                   f"{len(self.failed_paths)} failed paths, "
                   f"{len(self.npc_interactions)} NPCs recorded")

    def _load_from_cache(self):
        """Load memory from persistent cache"""
        try:
            cache_file = self.cache_dir / "strategic_memory.json"
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    data = json.load(f)

                # Load battle outcomes
                for key, battle_data in data.get('battles', {}).items():
                    self.battle_outcomes[key] = BattleMemory(**battle_data)

                # Load failed paths
                for path_data in data.get('failed_paths', []):
                    start = tuple(path_data['start'])
                    end = tuple(path_data['end'])
                    self.failed_paths.add((start, end))
                    path_key = f"{start[0]}_{start[1]}_to_{end[0]}_{end[1]}"
                    self.path_attempts[path_key] = path_data.get('attempts', 1)

                # Load NPC interactions
                for key, npc_data in data.get('npcs', {}).items():
                    npc_data['coords'] = tuple(npc_data['coords'])
                    self.npc_interactions[key] = NPCMemory(**npc_data)

                # Load item locations
                for key, item_data in data.get('items', {}).items():
                    item_data['coords'] = tuple(item_data['coords'])
                    self.item_locations[key] = ItemMemory(**item_data)

                # Load warp connections
                for key, warp_data in data.get('warps', {}).items():
                    warp_data['from_coords'] = tuple(warp_data['from_coords'])
                    warp_data['to_coords'] = tuple(warp_data['to_coords'])
                    self.warp_connections[key] = WarpMemory(**warp_data)

                # Load statistics
                stats = data.get('statistics', {})
                self.total_battles = stats.get('total_battles', 0)
                self.battles_won = stats.get('battles_won', 0)
                self.battles_lost = stats.get('battles_lost', 0)
                self.paths_blocked = stats.get('paths_blocked', 0)
                self.npcs_encountered = stats.get('npcs_encountered', 0)

                logger.info(f"Loaded strategic memory from cache: {len(self.battle_outcomes)} battles")
        except Exception as e:
            logger.warning(f"Failed to load strategic memory cache: {e}")

    def save_to_cache(self):
        """Save memory to persistent cache"""
        try:
            cache_file = self.cache_dir / "strategic_memory.json"

            # Convert to serializable format
            data = {
                'battles': {
                    key: {
                        **asdict(battle),
                        'player_team': list(battle.player_team),
                        'opponent_team': list(battle.opponent_team)
                    }
                    for key, battle in self.battle_outcomes.items()
                },
                'failed_paths': [
                    {
                        'start': list(start),
                        'end': list(end),
                        'attempts': self.path_attempts.get(f"{start[0]}_{start[1]}_to_{end[0]}_{end[1]}", 1)
                    }
                    for start, end in self.failed_paths
                ],
                'npcs': {
                    key: {
                        **asdict(npc),
                        'coords': list(npc.coords)
                    }
                    for key, npc in self.npc_interactions.items()
                },
                'items': {
                    key: {
                        **asdict(item),
                        'coords': list(item.coords)
                    }
                    for key, item in self.item_locations.items()
                },
                'warps': {
                    key: {
                        **asdict(warp),
                        'from_coords': list(warp.from_coords),
                        'to_coords': list(warp.to_coords)
                    }
                    for key, warp in self.warp_connections.items()
                },
                'statistics': {
                    'total_battles': self.total_battles,
                    'battles_won': self.battles_won,
                    'battles_lost': self.battles_lost,
                    'paths_blocked': self.paths_blocked,
                    'npcs_encountered': self.npcs_encountered
                }
            }

            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved strategic memory to cache")
        except Exception as e:
            logger.error(f"Failed to save strategic memory: {e}")

    def record_battle(
        self,
        trainer_name: str,
        location: str,
        outcome: str,
        player_team: List[str],
        opponent_team: List[str],
        turns: int,
        notes: str = ""
    ):
        """Record a battle outcome"""
        battle_key = f"{location}_{trainer_name}".replace(" ", "_")

        battle_memory = BattleMemory(
            trainer_name=trainer_name,
            location=location,
            outcome=outcome,
            player_team=player_team,
            opponent_team=opponent_team,
            turns=turns,
            timestamp=datetime.now().isoformat(),
            notes=notes
        )

        self.battle_outcomes[battle_key] = battle_memory
        self.total_battles += 1

        if outcome == "win":
            self.battles_won += 1
        elif outcome == "loss":
            self.battles_lost += 1

        logger.info(f"Recorded battle: {trainer_name} - {outcome} ({turns} turns)")
        self.save_to_cache()

    def get_battle_history(self, trainer_name: str = None, location: str = None) -> List[BattleMemory]:
        """Get battle history, optionally filtered"""
        results = []

        for battle in self.battle_outcomes.values():
            if trainer_name and trainer_name not in battle.trainer_name:
                continue
            if location and location not in battle.location:
                continue
            results.append(battle)

        return sorted(results, key=lambda b: b.timestamp, reverse=True)

    def record_failed_path(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        reason: str
    ):
        """Record a path that failed to navigate"""
        path_tuple = (start, end)
        path_key = f"{start[0]}_{start[1]}_to_{end[0]}_{end[1]}"

        self.failed_paths.add(path_tuple)
        self.path_attempts[path_key] += 1
        self.paths_blocked += 1

        attempts = self.path_attempts[path_key]
        logger.info(f"Recorded failed path: {start} -> {end} ({reason}) - attempt #{attempts}")

        # Save periodically
        if self.paths_blocked % 10 == 0:
            self.save_to_cache()

    def is_path_blocked(self, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
        """Check if a path is known to be blocked"""
        return (start, end) in self.failed_paths

    def get_path_attempts(self, start: Tuple[int, int], end: Tuple[int, int]) -> int:
        """Get number of times a path was attempted"""
        path_key = f"{start[0]}_{start[1]}_to_{end[0]}_{end[1]}"
        return self.path_attempts.get(path_key, 0)

    def record_npc_interaction(
        self,
        npc_id: str,
        location: str,
        coords: Tuple[int, int],
        interaction_type: str,
        result: str,
        dialogue_length: int = 0,
        important: bool = False
    ):
        """Record an NPC interaction"""
        npc_memory = NPCMemory(
            npc_id=npc_id,
            location=location,
            coords=coords,
            interaction_type=interaction_type,
            result=result,
            dialogue_length=dialogue_length,
            timestamp=datetime.now().isoformat(),
            important=important
        )

        self.npc_interactions[npc_id] = npc_memory
        self.npcs_encountered += 1

        logger.info(f"Recorded NPC interaction: {npc_id} ({interaction_type}) - {result}")

        # Save important NPCs immediately
        if important:
            self.save_to_cache()

    def get_npc_info(self, npc_id: str = None, location: str = None) -> List[NPCMemory]:
        """Get NPC interaction history"""
        results = []

        for npc in self.npc_interactions.values():
            if npc_id and npc.npc_id != npc_id:
                continue
            if location and location not in npc.location:
                continue
            results.append(npc)

        return results

    def record_item_location(
        self,
        item_name: str,
        location: str,
        coords: Tuple[int, int],
        obtained: bool = False
    ):
        """Record an item location"""
        item_key = f"{location}_{item_name}_{coords[0]}_{coords[1]}".replace(" ", "_")

        item_memory = ItemMemory(
            item_name=item_name,
            location=location,
            coords=coords,
            obtained=obtained,
            timestamp=datetime.now().isoformat()
        )

        self.item_locations[item_key] = item_memory
        logger.info(f"Recorded item: {item_name} at {location} {coords} (obtained: {obtained})")

        self.save_to_cache()

    def get_unobtained_items(self, location: str = None) -> List[ItemMemory]:
        """Get list of items not yet obtained"""
        results = []

        for item in self.item_locations.values():
            if item.obtained:
                continue
            if location and location not in item.location:
                continue
            results.append(item)

        return results

    def record_warp(
        self,
        from_location: str,
        from_coords: Tuple[int, int],
        to_location: str,
        to_coords: Tuple[int, int],
        warp_type: str
    ):
        """Record a warp/portal connection"""
        warp_key = f"{from_location}_{from_coords[0]}_{from_coords[1]}".replace(" ", "_")

        warp_memory = WarpMemory(
            from_location=from_location,
            from_coords=from_coords,
            to_location=to_location,
            to_coords=to_coords,
            warp_type=warp_type,
            timestamp=datetime.now().isoformat()
        )

        self.warp_connections[warp_key] = warp_memory
        logger.info(f"Recorded warp: {from_location} {from_coords} -> {to_location} {to_coords}")

        self.save_to_cache()

    def get_warps_from_location(self, location: str) -> List[WarpMemory]:
        """Get all warps from a location"""
        return [
            warp for warp in self.warp_connections.values()
            if warp.from_location == location
        ]

    def format_memory_for_prompt(self, current_location: str = None) -> str:
        """Format memory as a prompt section for LLM"""
        lines = ["📚 STRATEGIC MEMORY:"]

        # Battle statistics
        if self.total_battles > 0:
            win_rate = (self.battles_won / self.total_battles) * 100 if self.total_battles > 0 else 0
            lines.append(f"Battles: {self.battles_won}W-{self.battles_lost}L ({win_rate:.0f}% win rate)")

        # Recent battle lessons
        recent_battles = self.get_battle_history()[:3]
        if recent_battles:
            lines.append("\nRecent Battle Lessons:")
            for battle in recent_battles:
                lines.append(f"  • {battle.trainer_name}: {battle.outcome} "
                           f"(team: {', '.join(battle.player_team[:2])})")

        # Failed paths to avoid
        if current_location and self.failed_paths:
            lines.append("\n⚠️ Blocked Paths (AVOID THESE):")
            count = 0
            for start, end in sorted(self.failed_paths, key=lambda p: self.get_path_attempts(p[0], p[1]), reverse=True):
                attempts = self.get_path_attempts(start, end)
                if attempts >= 2:  # Only show repeatedly failed paths
                    lines.append(f"  • {start} -> {end} (failed {attempts}x)")
                    count += 1
                    if count >= 5:  # Max 5 to keep prompt manageable
                        break

        # Important NPCs
        important_npcs = [npc for npc in self.npc_interactions.values() if npc.important]
        if important_npcs and current_location:
            location_npcs = [npc for npc in important_npcs if npc.location == current_location]
            if location_npcs:
                lines.append(f"\n📍 Important NPCs in {current_location}:")
                for npc in location_npcs[:3]:
                    lines.append(f"  • {npc.npc_id}: {npc.result}")

        # Nearby items
        if current_location:
            nearby_items = self.get_unobtained_items(current_location)
            if nearby_items:
                lines.append(f"\n🎁 Items in {current_location}:")
                for item in nearby_items[:3]:
                    lines.append(f"  • {item.item_name} at {item.coords}")

        # Known warps
        if current_location:
            warps = self.get_warps_from_location(current_location)
            if warps:
                lines.append(f"\n🚪 Warps from {current_location}:")
                for warp in warps[:3]:
                    lines.append(f"  • {warp.from_coords} -> {warp.to_location}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            'total_battles': self.total_battles,
            'battles_won': self.battles_won,
            'battles_lost': self.battles_lost,
            'win_rate': (self.battles_won / self.total_battles * 100) if self.total_battles > 0 else 0,
            'failed_paths': len(self.failed_paths),
            'npcs_encountered': self.npcs_encountered,
            'items_found': len(self.item_locations),
            'items_obtained': sum(1 for item in self.item_locations.values() if item.obtained),
            'warps_discovered': len(self.warp_connections)
        }

    def clear_session_data(self):
        """Clear data from current session (keep persistent learnings)"""
        # Keep battle outcomes and failed paths (valuable lessons)
        # Clear temporary items and NPCs that might change
        logger.info("Clearing session data from strategic memory")
        # Intentionally keeping most data - this is strategic memory after all
        self.save_to_cache()
