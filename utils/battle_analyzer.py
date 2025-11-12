"""
Battle Analyzer for Pokemon Emerald

Provides type effectiveness calculations and optimal move selection for battles.
Phase 1.3 implementation from TRACK2_SIMPLE_AGENT_OPTIMIZATION_PLAN.md
"""

import logging
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)

# Type effectiveness chart for Pokemon Gen 3 (Emerald)
# Format: TYPE_CHART[attacking_type][defending_type] = multiplier
TYPE_CHART = {
    "Normal": {
        "Rock": 0.5, "Ghost": 0, "Steel": 0.5
    },
    "Fire": {
        "Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0,
        "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0
    },
    "Water": {
        "Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0,
        "Rock": 2.0, "Dragon": 0.5
    },
    "Electric": {
        "Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0,
        "Flying": 2.0, "Dragon": 0.5
    },
    "Grass": {
        "Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5,
        "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0,
        "Dragon": 0.5, "Steel": 0.5
    },
    "Ice": {
        "Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5,
        "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5
    },
    "Fighting": {
        "Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5,
        "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0,
        "Dark": 2.0, "Steel": 2.0
    },
    "Poison": {
        "Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5,
        "Ghost": 0.5, "Steel": 0
    },
    "Ground": {
        "Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0,
        "Flying": 0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0
    },
    "Flying": {
        "Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0,
        "Rock": 0.5, "Steel": 0.5
    },
    "Psychic": {
        "Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0,
        "Steel": 0.5
    },
    "Bug": {
        "Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5,
        "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0,
        "Steel": 0.5
    },
    "Rock": {
        "Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5,
        "Flying": 2.0, "Bug": 2.0, "Steel": 0.5
    },
    "Ghost": {
        "Normal": 0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5,
        "Steel": 0.5
    },
    "Dragon": {
        "Dragon": 2.0, "Steel": 0.5
    },
    "Dark": {
        "Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5,
        "Steel": 0.5
    },
    "Steel": {
        "Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0,
        "Rock": 2.0, "Steel": 0.5
    }
}


class BattleAnalyzer:
    """Analyzes battle situations and recommends optimal moves"""

    def __init__(self):
        self.type_chart = TYPE_CHART
        logger.info("Battle Analyzer initialized with type effectiveness data")

    def get_type_effectiveness(self, attack_type: str, defend_types: List[str]) -> float:
        """
        Calculate type effectiveness multiplier for an attack.

        Args:
            attack_type: Type of the attacking move
            defend_types: List of defending Pokemon's types (1 or 2 types)

        Returns:
            float: Damage multiplier (0, 0.25, 0.5, 1.0, 2.0, or 4.0)
        """
        if not attack_type or attack_type == "???":
            return 1.0  # Unknown type

        multiplier = 1.0

        for defend_type in defend_types:
            if defend_type and defend_type != "???":
                # Get effectiveness from chart
                type_matchup = self.type_chart.get(attack_type, {})
                effectiveness = type_matchup.get(defend_type, 1.0)
                multiplier *= effectiveness

        return multiplier

    def calculate_move_score(
        self,
        move_name: str,
        move_type: str,
        move_power: int,
        attacker_types: List[str],
        defender_types: List[str],
        move_pp: int
    ) -> Tuple[float, str]:
        """
        Calculate a score for how good a move is in the current situation.

        Args:
            move_name: Name of the move
            move_type: Type of the move
            move_power: Base power of the move
            attacker_types: Types of the attacking Pokemon
            defender_types: Types of the defending Pokemon
            move_pp: Remaining PP for the move

        Returns:
            Tuple of (score, explanation)
        """
        if move_power == 0 or move_power is None:
            # Status move or unknown power
            return (10.0, "Status move - situational")

        # Base score from power
        score = float(move_power)
        explanation_parts = [f"Base power: {move_power}"]

        # STAB bonus (Same Type Attack Bonus = 1.5x)
        has_stab = move_type in attacker_types
        if has_stab:
            score *= 1.5
            explanation_parts.append("STAB bonus (1.5x)")

        # Type effectiveness
        effectiveness = self.get_type_effectiveness(move_type, defender_types)
        score *= effectiveness

        if effectiveness == 0:
            explanation_parts.append("NO EFFECT (0x)")
        elif effectiveness == 0.25:
            explanation_parts.append("Not very effective (0.25x)")
        elif effectiveness == 0.5:
            explanation_parts.append("Not very effective (0.5x)")
        elif effectiveness == 2.0:
            explanation_parts.append("Super effective (2x)")
        elif effectiveness == 4.0:
            explanation_parts.append("Super effective (4x)")
        else:
            explanation_parts.append("Neutral effectiveness (1x)")

        # PP consideration - penalize moves with low PP
        if move_pp == 0:
            score = 0
            explanation_parts.append("NO PP REMAINING")
        elif move_pp <= 2:
            score *= 0.8
            explanation_parts.append(f"Low PP ({move_pp} remaining)")

        explanation = " | ".join(explanation_parts)
        return (score, explanation)

    def get_best_move(
        self,
        your_pokemon: Dict[str, Any],
        opponent_pokemon: Dict[str, Any],
        available_moves: List[Dict[str, Any]]
    ) -> Tuple[Optional[int], str]:
        """
        Determine the best move to use in battle.

        Args:
            your_pokemon: Your active Pokemon's data
            opponent_pokemon: Opponent's active Pokemon's data
            available_moves: List of available move data

        Returns:
            Tuple of (move_index, reasoning)
            move_index is 0-3 for the move to select, None if can't determine
        """
        try:
            if not available_moves or not opponent_pokemon:
                return (None, "Insufficient battle data")

            # Get Pokemon types
            attacker_types = your_pokemon.get('types', [])
            defender_types = opponent_pokemon.get('types', [])

            if not attacker_types:
                attacker_types = ['Normal']  # Default
            if not defender_types:
                defender_types = ['Normal']  # Default

            # Score each move
            move_scores = []
            for i, move_data in enumerate(available_moves):
                if not move_data:
                    continue

                move_name = move_data.get('name', f'Move {i+1}')
                move_type = move_data.get('type', 'Normal')
                move_power = move_data.get('power', 0)
                move_pp = move_data.get('pp', 0)

                score, explanation = self.calculate_move_score(
                    move_name, move_type, move_power,
                    attacker_types, defender_types, move_pp
                )

                move_scores.append({
                    'index': i,
                    'name': move_name,
                    'score': score,
                    'explanation': explanation
                })

            if not move_scores:
                return (None, "No valid moves available")

            # Sort by score (highest first)
            move_scores.sort(key=lambda x: x['score'], reverse=True)

            # Get best move
            best_move = move_scores[0]

            # Build reasoning
            reasoning_parts = [
                f"Best move: {best_move['name']} (Move {best_move['index'] + 1})",
                f"Score: {best_move['score']:.1f}",
                best_move['explanation']
            ]

            # Show alternative if close
            if len(move_scores) > 1:
                second_best = move_scores[1]
                if second_best['score'] > 0 and second_best['score'] >= best_move['score'] * 0.8:
                    reasoning_parts.append(
                        f"Alternative: {second_best['name']} (score: {second_best['score']:.1f})"
                    )

            reasoning = " | ".join(reasoning_parts)

            return (best_move['index'], reasoning)

        except Exception as e:
            logger.error(f"Error analyzing best move: {e}", exc_info=True)
            return (None, f"Analysis error: {e}")

    def should_switch(
        self,
        your_pokemon: Dict[str, Any],
        opponent_pokemon: Dict[str, Any],
        your_party: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[int], str]:
        """
        Determine if switching Pokemon is recommended.

        Args:
            your_pokemon: Your active Pokemon's data
            opponent_pokemon: Opponent's active Pokemon's data
            your_party: Your full party of Pokemon

        Returns:
            Tuple of (should_switch, switch_to_index, reasoning)
        """
        try:
            # Don't switch if current Pokemon is healthy
            current_hp_pct = your_pokemon.get('hp_percentage', 100)
            if current_hp_pct > 50:
                return (False, None, "Current Pokemon is healthy")

            # Check type matchup
            your_types = your_pokemon.get('types', ['Normal'])
            opponent_types = opponent_pokemon.get('types', ['Normal'])

            # Calculate how effective opponent's likely moves are against us
            # (Simplified: assume opponent has a move of their own type)
            worst_effectiveness = 1.0
            for opp_type in opponent_types:
                effectiveness = self.get_type_effectiveness(opp_type, your_types)
                if effectiveness > worst_effectiveness:
                    worst_effectiveness = effectiveness

            # If we're weak to opponent AND low HP, consider switching
            if worst_effectiveness >= 2.0 and current_hp_pct < 40:
                # Find a better matchup in party
                for i, party_member in enumerate(your_party):
                    if not party_member or i == 0:  # Skip empty slots and current Pokemon
                        continue

                    member_hp_pct = party_member.get('hp_percentage', 0)
                    if member_hp_pct < 25:  # Skip weak Pokemon
                        continue

                    member_types = party_member.get('types', ['Normal'])

                    # Calculate how effective opponent's moves are against this Pokemon
                    member_effectiveness = 1.0
                    for opp_type in opponent_types:
                        effectiveness = self.get_type_effectiveness(opp_type, member_types)
                        if effectiveness > member_effectiveness:
                            member_effectiveness = effectiveness

                    # If this Pokemon resists opponent better, recommend switch
                    if member_effectiveness < worst_effectiveness:
                        reasoning = (
                            f"Switch recommended: {party_member.get('species', 'Pokemon')} "
                            f"resists opponent better ({member_effectiveness}x vs {worst_effectiveness}x)"
                        )
                        return (True, i, reasoning)

            return (False, None, "No better switch available")

        except Exception as e:
            logger.error(f"Error analyzing switch decision: {e}", exc_info=True)
            return (False, None, f"Switch analysis error: {e}")

    def format_battle_analysis(
        self,
        your_pokemon: Dict[str, Any],
        opponent_pokemon: Dict[str, Any],
        available_moves: List[Dict[str, Any]],
        your_party: List[Dict[str, Any]] = None
    ) -> str:
        """
        Format a complete battle analysis for LLM prompt.

        Args:
            your_pokemon: Your active Pokemon's data
            opponent_pokemon: Opponent's active Pokemon's data
            available_moves: List of available moves
            your_party: Your full party (optional, for switch analysis)

        Returns:
            Formatted battle analysis string
        """
        lines = ["🎯 BATTLE ANALYSIS:"]

        # Best move recommendation
        best_move_idx, move_reasoning = self.get_best_move(
            your_pokemon, opponent_pokemon, available_moves
        )

        if best_move_idx is not None:
            lines.append(f"RECOMMENDED MOVE: {best_move_idx + 1}")
            lines.append(f"  {move_reasoning}")
        else:
            lines.append(f"MOVE ANALYSIS: {move_reasoning}")

        # Switch recommendation (if party data available)
        if your_party and len(your_party) > 1:
            should_sw, switch_idx, switch_reasoning = self.should_switch(
                your_pokemon, opponent_pokemon, your_party
            )
            if should_sw and switch_idx is not None:
                lines.append("")
                lines.append(f"SWITCH RECOMMENDED: Party member {switch_idx + 1}")
                lines.append(f"  {switch_reasoning}")

        return "\n".join(lines)
