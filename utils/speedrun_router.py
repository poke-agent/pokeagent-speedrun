"""
Speedrun Router for Pokemon Emerald

Phase 2.2 implementation from TRACK2_SIMPLE_AGENT_OPTIMIZATION_PLAN.md

Provides optimal route planning based on known Pokemon Emerald speedrun strategies.
Defines checkpoints, recommended team composition, and critical path milestones.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


@dataclass
class RouteCheckpoint:
    """A checkpoint in the speedrun route"""
    checkpoint_id: str
    name: str
    location: str
    coords: Optional[Tuple[int, int]]
    milestone_id: Optional[str]  # Links to emulator milestone
    description: str
    optimal_actions: int  # Expected action count to reach this point
    prerequisites: List[str] = None  # Required previous checkpoints
    optional: bool = False  # Can be skipped
    recommended_team: List[str] = None  # Recommended Pokemon team
    key_items: List[str] = None  # Items needed or obtained here
    notes: str = ""


class SpeedrunRouter:
    """
    Optimal route planning for Pokemon Emerald speedruns.

    Based on established speedrun strategies and world records.
    Helps agent stay on the critical path and avoid unnecessary detours.
    """

    def __init__(self):
        self.checkpoints: Dict[str, RouteCheckpoint] = {}
        self.current_checkpoint_index = 0
        self.completed_checkpoints: List[str] = []

        # Initialize the optimal route
        self._initialize_emerald_route()

        logger.info(f"Speedrun Router initialized with {len(self.checkpoints)} checkpoints")

    def _initialize_emerald_route(self):
        """Initialize the optimal Emerald speedrun route"""

        route = [
            RouteCheckpoint(
                checkpoint_id="cp_000",
                name="Game Start",
                location="TITLE_SEQUENCE",
                coords=None,
                milestone_id="GAME_RUNNING",
                description="Start game and skip intro quickly",
                optimal_actions=20,
                recommended_team=[],
                key_items=[],
                notes="Mash A to skip naming screens and intro"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_001",
                name="Moving Van Exit",
                location="MOVING_VAN",
                coords=(5, 3),  # Approximate
                milestone_id="INTRO_CUTSCENE_COMPLETE",
                description="Exit the moving van by moving RIGHT",
                optimal_actions=50,
                prerequisites=["cp_000"],
                notes="Move RIGHT to exit van, triggers intro cutscene"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_002",
                name="Player House 1F",
                location="LITTLEROOT_TOWN_PLAYERS_HOUSE_1F",
                coords=None,
                milestone_id="PLAYER_HOUSE_ENTERED",
                description="Enter player's house",
                optimal_actions=60,
                prerequisites=["cp_001"],
                notes="Go DOWN from van exit, then RIGHT into house"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_003",
                name="Player House 2F",
                location="LITTLEROOT_TOWN_PLAYERS_HOUSE_2F",
                coords=None,
                milestone_id="PLAYER_BEDROOM",
                description="Go upstairs to bedroom and set clock",
                optimal_actions=100,
                prerequisites=["cp_002"],
                recommended_team=[],
                key_items=["Clock Set"],
                notes="Go UP stairs, interact with clock at (5,1), then go DOWN"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_004",
                name="Route 101",
                location="ROUTE101",
                coords=None,
                milestone_id="ROUTE_101",
                description="Travel north to Route 101, trigger Birch cutscene",
                optimal_actions=150,
                prerequisites=["cp_003"],
                notes="Exit house, go UP/LEFT to reach Route 101"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_005",
                name="Get Starter",
                location="ROUTE101",
                coords=None,
                milestone_id="STARTER_CHOSEN",
                description="Choose Mudkip as starter (best for speedruns)",
                optimal_actions=200,
                prerequisites=["cp_004"],
                recommended_team=["Mudkip"],
                key_items=["Mudkip"],
                notes="Mudkip is optimal - strong vs Roxanne (Rock) and Flannery (Fire)"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_006",
                name="Birch's Lab",
                location="LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB",
                coords=None,
                milestone_id="BIRCH_LAB_VISITED",
                description="Return to lab, get Pokedex",
                optimal_actions=300,
                prerequisites=["cp_005"],
                recommended_team=["Mudkip"],
                key_items=["Pokedex", "Pokeballs x5"],
                notes="Talk to Birch, receive Pokedex and Pokeballs"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_007",
                name="Oldale Town",
                location="OLDALE_TOWN",
                coords=None,
                milestone_id="OLDALE_TOWN",
                description="Travel to Oldale Town through Route 101",
                optimal_actions=400,
                prerequisites=["cp_006"],
                recommended_team=["Mudkip"],
                notes="Go north, avoid wild Pokemon battles when possible"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_008",
                name="Route 103",
                location="ROUTE103",
                coords=None,
                milestone_id="ROUTE_103",
                description="Visit Route 103 to meet rival",
                optimal_actions=500,
                prerequisites=["cp_007"],
                recommended_team=["Mudkip"],
                optional=True,
                notes="Optional - can skip and return later"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_009",
                name="Route 102",
                location="ROUTE102",
                coords=None,
                milestone_id="ROUTE_102",
                description="Travel through Route 102",
                optimal_actions=600,
                prerequisites=["cp_007"],
                recommended_team=["Mudkip"],
                notes="Heading toward Petalburg City"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_010",
                name="Petalburg City",
                location="PETALBURG_CITY",
                coords=None,
                milestone_id="PETALBURG_CITY",
                description="Arrive in Petalburg City",
                optimal_actions=700,
                prerequisites=["cp_009"],
                recommended_team=["Mudkip"],
                notes="Don't fight Norman's gym yet (5th gym badge)"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_011",
                name="Petalburg Gym",
                location="PETALBURG_CITY_GYM",
                coords=None,
                milestone_id="DAD_FIRST_MEETING",
                description="Meet Dad at gym, get Wally tutorial",
                optimal_actions=800,
                prerequisites=["cp_010"],
                recommended_team=["Mudkip"],
                notes="Required story event, then leave"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_012",
                name="Route 104 South",
                location="ROUTE104",
                coords=None,
                milestone_id="ROUTE_104_SOUTH",
                description="Travel through southern Route 104",
                optimal_actions=900,
                prerequisites=["cp_011"],
                recommended_team=["Mudkip"],
                notes="Heading toward Petalburg Woods"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_013",
                name="Petalburg Woods",
                location="PETALBURG_WOODS",
                coords=None,
                milestone_id="PETALBURG_WOODS",
                description="Navigate through Petalburg Woods",
                optimal_actions=1000,
                prerequisites=["cp_012"],
                recommended_team=["Mudkip"],
                notes="Fight Team Aqua Grunt (required)"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_014",
                name="Aqua Grunt Battle",
                location="PETALBURG_WOODS",
                coords=None,
                milestone_id="TEAM_AQUA_GRUNT_DEFEATED",
                description="Defeat Team Aqua Grunt (Poochyena)",
                optimal_actions=1100,
                prerequisites=["cp_013"],
                recommended_team=["Mudkip"],
                notes="Required battle, use Mud Shot/Water Gun"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_015",
                name="Route 104 North",
                location="ROUTE104",
                coords=None,
                milestone_id="ROUTE_104_NORTH",
                description="Exit woods to northern Route 104",
                optimal_actions=1200,
                prerequisites=["cp_014"],
                recommended_team=["Mudkip"],
                notes="Almost to Rustboro City"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_016",
                name="Rustboro City",
                location="RUSTBORO_CITY",
                coords=None,
                milestone_id="RUSTBORO_CITY",
                description="Arrive in Rustboro City",
                optimal_actions=1300,
                prerequisites=["cp_015"],
                recommended_team=["Mudkip"],
                key_items=["Devon Goods"],
                notes="Deliver Devon Goods, prepare for first gym"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_017",
                name="Rustboro Gym",
                location="RUSTBORO_CITY_GYM",
                coords=None,
                milestone_id="RUSTBORO_GYM_ENTERED",
                description="Enter Rustboro Gym",
                optimal_actions=1400,
                prerequisites=["cp_016"],
                recommended_team=["Mudkip (Lv 12-14)"],
                notes="Mudkip should know Water Gun or Mud Shot"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_018",
                name="Roxanne Battle",
                location="RUSTBORO_CITY_GYM",
                coords=None,
                milestone_id="ROXANNE_DEFEATED",
                description="Defeat Gym Leader Roxanne",
                optimal_actions=1500,
                prerequisites=["cp_017"],
                recommended_team=["Mudkip (Lv 14+)"],
                key_items=["Stone Badge", "TM39 Rock Tomb"],
                notes="Roxanne has Geodude (Lv 12), Geodude (Lv 12), Nosepass (Lv 15)"
            ),
            RouteCheckpoint(
                checkpoint_id="cp_019",
                name="First Badge Complete",
                location="RUSTBORO_CITY_GYM",
                coords=None,
                milestone_id="FIRST_GYM_COMPLETE",
                description="Receive Stone Badge (1/8)",
                optimal_actions=1600,
                prerequisites=["cp_018"],
                recommended_team=["Mudkip (Lv 15+)"],
                key_items=["Stone Badge"],
                notes="First gym badge obtained! Continue to Dewford Town"
            ),
        ]

        # Build checkpoint dictionary
        for checkpoint in route:
            self.checkpoints[checkpoint.checkpoint_id] = checkpoint

        logger.info(f"Initialized Emerald speedrun route with {len(route)} checkpoints")

    def get_next_checkpoint(self, current_milestones: Dict[str, bool]) -> Optional[RouteCheckpoint]:
        """
        Get the next recommended checkpoint based on completed milestones.

        Args:
            current_milestones: Dict of milestone_id -> completed status

        Returns:
            Next checkpoint to pursue, or None if route complete
        """
        # Find first incomplete checkpoint
        for checkpoint_id in sorted(self.checkpoints.keys()):
            checkpoint = self.checkpoints[checkpoint_id]

            # Skip if already completed
            if checkpoint_id in self.completed_checkpoints:
                continue

            # Check if prerequisites are met
            if checkpoint.prerequisites:
                prereqs_met = all(
                    prereq in self.completed_checkpoints
                    for prereq in checkpoint.prerequisites
                )
                if not prereqs_met:
                    continue

            # Check if milestone already achieved
            if checkpoint.milestone_id:
                if current_milestones.get(checkpoint.milestone_id, False):
                    self.completed_checkpoints.append(checkpoint_id)
                    logger.info(f"✅ Checkpoint completed: {checkpoint.name}")
                    continue

            # This is the next checkpoint
            return checkpoint

        # All checkpoints complete!
        return None

    def get_checkpoint_by_location(self, location: str) -> Optional[RouteCheckpoint]:
        """Find checkpoint by location name"""
        for checkpoint in self.checkpoints.values():
            if checkpoint.location == location:
                return checkpoint
        return None

    def get_recommended_team_at_checkpoint(self, checkpoint_id: str) -> List[str]:
        """Get recommended team composition at a checkpoint"""
        checkpoint = self.checkpoints.get(checkpoint_id)
        if checkpoint and checkpoint.recommended_team:
            return checkpoint.recommended_team
        return []

    def is_on_critical_path(self, location: str) -> bool:
        """Check if location is on the critical speedrun path"""
        # Check if any non-optional checkpoint has this location
        for checkpoint in self.checkpoints.values():
            if checkpoint.location == location and not checkpoint.optional:
                return True
        return False

    def get_progress_percentage(self) -> float:
        """Calculate speedrun progress as percentage"""
        if not self.checkpoints:
            return 0.0
        return (len(self.completed_checkpoints) / len(self.checkpoints)) * 100

    def get_efficiency_rating(self, current_actions: int) -> Tuple[str, str]:
        """
        Rate current efficiency vs optimal speedrun.

        Returns:
            Tuple of (rating, description)
        """
        if not self.completed_checkpoints:
            return ("on-pace", "Just started")

        # Get last completed checkpoint
        last_checkpoint_id = self.completed_checkpoints[-1]
        checkpoint = self.checkpoints.get(last_checkpoint_id)

        if not checkpoint:
            return ("unknown", "Cannot determine")

        optimal = checkpoint.optimal_actions
        efficiency = optimal / current_actions if current_actions > 0 else 0

        if efficiency >= 0.9:
            return ("excellent", f"Ahead of pace! ({current_actions} vs {optimal} optimal)")
        elif efficiency >= 0.7:
            return ("good", f"On pace ({current_actions} vs {optimal} optimal)")
        elif efficiency >= 0.5:
            return ("acceptable", f"Slightly behind ({current_actions} vs {optimal} optimal)")
        else:
            return ("slow", f"Significantly behind ({current_actions} vs {optimal} optimal)")

    def format_progress_for_prompt(self, current_milestones: Dict[str, bool], current_actions: int) -> str:
        """Format speedrun progress as a prompt section"""
        lines = ["🏁 SPEEDRUN PROGRESS:"]

        # Current progress
        progress_pct = self.get_progress_percentage()
        lines.append(f"Completion: {progress_pct:.1f}% ({len(self.completed_checkpoints)}/{len(self.checkpoints)} checkpoints)")

        # Efficiency rating
        rating, description = self.get_efficiency_rating(current_actions)
        rating_emoji = {"excellent": "🚀", "good": "✅", "acceptable": "⚠️", "slow": "🐌"}.get(rating, "❓")
        lines.append(f"Efficiency: {rating_emoji} {rating.upper()} - {description}")

        # Next checkpoint
        next_cp = self.get_next_checkpoint(current_milestones)
        if next_cp:
            lines.append(f"\n📍 NEXT CHECKPOINT: {next_cp.name}")
            lines.append(f"  Location: {next_cp.location}")
            lines.append(f"  Description: {next_cp.description}")
            if next_cp.recommended_team:
                lines.append(f"  Recommended Team: {', '.join(next_cp.recommended_team)}")
            if next_cp.notes:
                lines.append(f"  💡 TIP: {next_cp.notes}")
        else:
            lines.append("\n🎉 All checkpoints complete!")

        # Last few checkpoints
        recent = self.completed_checkpoints[-3:] if len(self.completed_checkpoints) >= 3 else self.completed_checkpoints
        if recent:
            lines.append(f"\nRecent Checkpoints:")
            for cp_id in recent:
                cp = self.checkpoints.get(cp_id)
                if cp:
                    lines.append(f"  ✅ {cp.name}")

        return "\n".join(lines)

    def get_speedrun_tips(self, location: str) -> List[str]:
        """Get location-specific speedrun tips"""
        tips = []

        # General tips
        general_tips = {
            "ROUTE101": [
                "Avoid wild battles when possible",
                "Mudkip is the optimal starter choice",
                "Save game after getting starter"
            ],
            "RUSTBORO_CITY_GYM": [
                "Mudkip should be Lv 14+ before challenging Roxanne",
                "Water Gun is super effective vs all her Pokemon",
                "Don't waste time grinding higher - Lv 14 is enough"
            ],
            "PETALBURG_WOODS": [
                "Team Aqua Grunt battle is required - cannot skip",
                "His Poochyena is Dark type - use Tackle/Water Gun",
                "Catch a Slakoth here if you want (optional)"
            ]
        }

        return general_tips.get(location, [])
