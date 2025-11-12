"""
Knowledge Manager for Pokemon Emerald AI Agent

Orchestrates KnowledgeParser and MapProvider to deliver contextual
guidance and visual aids based on current game state and milestone.

Part of the Knowledge Base Implementation Plan - Phase 3
"""

import logging
from typing import Any, Dict, List, Optional

from PIL import Image

from utils.knowledge_parser import KnowledgeParser, KnowledgeSection
from utils.map_provider import MapProvider, MapData

logger = logging.getLogger(__name__)


class KnowledgeManager:
    """
    Central orchestrator for the knowledge base system.

    Combines KnowledgeParser (text walkthrough) and MapProvider (visual maps)
    to provide comprehensive, context-aware guidance to the AI agent.
    """

    def __init__(
        self,
        knowledge_file: str = "data/knowledge/speedrun.md",
        maps_directory: str = "data/knowledge"
    ):
        """
        Initialize the knowledge manager.

        Args:
            knowledge_file: Path to speedrun.md walkthrough
            maps_directory: Directory containing map .png files
        """
        self.knowledge_file = knowledge_file
        self.maps_directory = maps_directory

        # Initialize components
        logger.info("Initializing KnowledgeManager...")

        self.parser = KnowledgeParser(knowledge_file)
        self.map_provider = MapProvider(maps_directory)

        # Parse knowledge once at initialization
        self.sections = self.parser.parse_markdown()

        logger.info(
            f"KnowledgeManager initialized: {len(self.sections)} sections, "
            f"{self.map_provider.get_cache_stats()['total_maps']} maps available"
        )

    def get_contextual_knowledge(
        self,
        milestone_id: str,
        location: str,
        context: str = "overworld"
    ) -> Dict[str, Any]:
        """
        Get all relevant knowledge for the current game state.

        Args:
            milestone_id: Current agent milestone (e.g., "STARTER_CHOSEN")
            location: Game location ID (e.g., "ROUTE101")
            context: Game context (overworld, battle, dialogue, menu)

        Returns:
            Dictionary containing:
                - current_section: KnowledgeSection object
                - map_image: PIL Image or None
                - formatted_guidance: Formatted text string
                - objectives: List of objective strings
                - tips: List of tip strings
                - trainers_ahead: List of trainer info
                - items_available: List of item info
                - pokemon_available: List of Pokemon encounters
        """
        result = {
            'current_section': None,
            'map_image': None,
            'formatted_guidance': "",
            'objectives': [],
            'tips': [],
            'trainers_ahead': [],
            'items_available': [],
            'pokemon_available': []
        }

        try:
            # Get knowledge section
            section = None

            # Try milestone first
            if milestone_id:
                section = self.parser.get_section_by_milestone(milestone_id)
                logger.debug(f"Found section by milestone {milestone_id}: {section.title if section else 'None'}")

            # Fallback to location
            if not section and location:
                section = self.parser.get_section_by_location(location)
                logger.debug(f"Found section by location {location}: {section.title if section else 'None'}")

            if not section:
                logger.warning(f"No knowledge section found for milestone={milestone_id}, location={location}")
                return result

            result['current_section'] = section
            result['objectives'] = section.objectives
            result['tips'] = section.tips
            result['trainers_ahead'] = section.trainers
            result['items_available'] = section.items
            result['pokemon_available'] = section.available_pokemon

            # Get map image
            map_data = None
            if milestone_id:
                map_data = self.map_provider.get_map_for_milestone(milestone_id)
            if not map_data and location:
                map_data = self.map_provider.get_map_for_location(location)

            if map_data and map_data.image:
                result['map_image'] = map_data.image
                logger.debug(f"Loaded map: {map_data.location_name} ({map_data.image.size[0]}x{map_data.image.size[1]})")

            # Format guidance text
            result['formatted_guidance'] = self._format_section_guidance(
                section,
                context,
                include_full_details=True
            )

            logger.info(f"Retrieved contextual knowledge for {section.title}")

        except Exception as e:
            logger.error(f"Error getting contextual knowledge: {e}", exc_info=True)

        return result

    def format_knowledge_for_prompt(
        self,
        milestone_id: str,
        location: str,
        context: str = "overworld",
        include_full_details: bool = True
    ) -> str:
        """
        Format knowledge as text to inject into VLM prompt.

        Args:
            milestone_id: Current milestone
            location: Current location
            context: Game context
            include_full_details: If False, returns compact version

        Returns:
            Formatted string ready for VLM prompt
        """
        # Get contextual knowledge
        knowledge = self.get_contextual_knowledge(milestone_id, location, context)

        if not knowledge['current_section']:
            return ""

        return knowledge['formatted_guidance']

    def _format_section_guidance(
        self,
        section: KnowledgeSection,
        context: str,
        include_full_details: bool = True
    ) -> str:
        """
        Format a knowledge section into readable guidance text.

        Args:
            section: KnowledgeSection to format
            context: Game context
            include_full_details: Include all details vs compact

        Returns:
            Formatted guidance string
        """
        lines = []

        # Header
        lines.append(f"📚 SPEEDRUN KNOWLEDGE - {section.title.upper()}:")
        lines.append("")

        # Location and description
        lines.append(f"LOCATION: {section.title}")
        if section.description:
            lines.append(f"DESCRIPTION: {section.description}")
        lines.append("")

        # Objectives (key goals)
        if section.objectives:
            lines.append("KEY OBJECTIVES:")
            for obj in section.objectives[:5]:  # Top 5 objectives
                lines.append(f"  • {obj}")
            lines.append("")

        # Battle context - show trainers
        if section.trainers and (context == "battle" or context == "overworld"):
            lines.append("TRAINERS/BATTLES:")
            for trainer in section.trainers[:5]:  # Limit to top 5
                lines.append(f"  • {trainer.name} ({trainer.trainer_class})")
                if trainer.pokemon:
                    pokemon_summary = ", ".join([
                        f"{p['species']} (Lv {p['level']})"
                        for p in trainer.pokemon[:3]  # Show up to 3 Pokemon
                    ])
                    lines.append(f"    Team: {pokemon_summary}")
                if trainer.prize_money:
                    lines.append(f"    Prize: ${trainer.prize_money}")
            lines.append("")

        # Items available
        if section.items and include_full_details:
            lines.append("ITEMS AVAILABLE:")
            for item in section.items[:8]:  # Top 8 items
                hidden_marker = " (hidden)" if item.is_hidden else ""
                hm_marker = f" [requires {item.requires_hm}]" if item.requires_hm else ""
                lines.append(f"  • {item.name}{hidden_marker}{hm_marker}")
                if len(item.location_detail) < 80:  # Don't show super long details
                    lines.append(f"    Location: {item.location_detail}")
            lines.append("")

        # Wild Pokemon encounters
        if section.available_pokemon and include_full_details:
            lines.append("WILD POKEMON:")
            for pokemon in section.available_pokemon[:6]:  # Top 6 species
                lines.append(f"  • {pokemon.species} (Lv {pokemon.level_range}, {pokemon.encounter_rate})")
            lines.append("")

        # Strategic tips
        if section.tips:
            lines.append("💡 SPEEDRUN TIPS:")
            for tip in section.tips[:5]:  # Top 5 tips
                # Clean up tip formatting
                tip_clean = tip.strip('*-• ').strip()
                if len(tip_clean) > 0 and len(tip_clean) < 200:
                    lines.append(f"  • {tip_clean}")
            lines.append("")

        # Subsections (like "Gym Leader Roxanne", "Birch's Lab")
        if include_full_details and section.subsections:
            important_subsections = [
                key for key in section.subsections.keys()
                if any(keyword in key for keyword in ["Gym Leader", "Lab", "Battle", "Meet"])
            ]
            if important_subsections:
                lines.append("IMPORTANT LOCATIONS/EVENTS:")
                for subsection_name in important_subsections[:3]:  # Top 3 subsections
                    lines.append(f"  • {subsection_name}")
                lines.append("")

        # Compact mode - just essentials
        if not include_full_details:
            # Keep only: description, objectives, trainers (if any), tips
            compact_lines = [lines[0], lines[1]]  # Header

            if section.description:
                compact_lines.append(f"DESCRIPTION: {section.description}")
                compact_lines.append("")

            if section.objectives:
                compact_lines.append("OBJECTIVES:")
                compact_lines.extend([f"  • {obj}" for obj in section.objectives[:3]])
                compact_lines.append("")

            if section.trainers:
                compact_lines.append(f"TRAINERS: {len(section.trainers)} battles ahead")
                compact_lines.append("")

            if section.tips:
                compact_lines.append("TIPS:")
                compact_lines.extend([f"  • {tip.strip()}" for tip in section.tips[:2]])

            return "\n".join(compact_lines)

        return "\n".join(lines)

    def get_map_image(
        self,
        milestone_id: str,
        location: str,
        max_size: Optional[int] = None
    ) -> Optional[Image.Image]:
        """
        Get map image for current location/milestone.

        Args:
            milestone_id: Current milestone
            location: Current location
            max_size: Optional max dimension for resizing (e.g., 800)

        Returns:
            PIL Image or None
        """
        try:
            # Try milestone first
            map_data = None
            if milestone_id:
                map_data = self.map_provider.get_map_for_milestone(milestone_id)

            # Fallback to location
            if not map_data and location:
                map_data = self.map_provider.get_map_for_location(location)

            if not map_data or not map_data.image:
                logger.debug(f"No map image available for milestone={milestone_id}, location={location}")
                return None

            # Resize if requested
            if max_size:
                return self.map_provider.resize_map(map_data, max_size)

            return map_data.image

        except Exception as e:
            logger.error(f"Error getting map image: {e}", exc_info=True)
            return None

    def get_battle_strategy(
        self,
        milestone_id: str,
        location: str,
        trainer_name: Optional[str] = None
    ) -> str:
        """
        Get specific battle strategy for current location.

        Args:
            milestone_id: Current milestone
            location: Current location
            trainer_name: Optional specific trainer name

        Returns:
            Battle strategy text
        """
        knowledge = self.get_contextual_knowledge(milestone_id, location, context="battle")

        if not knowledge['current_section']:
            return ""

        lines = []
        lines.append("⚔️  BATTLE STRATEGY:")
        lines.append("")

        # Find relevant trainer
        target_trainer = None
        if trainer_name:
            for trainer in knowledge['trainers_ahead']:
                if trainer_name.lower() in trainer.name.lower():
                    target_trainer = trainer
                    break
        elif knowledge['trainers_ahead']:
            # Use first trainer (likely the gym leader or key battle)
            target_trainer = knowledge['trainers_ahead'][0]

        if target_trainer:
            lines.append(f"OPPONENT: {target_trainer.name} ({target_trainer.trainer_class})")

            if target_trainer.pokemon:
                lines.append(f"TEAM: {len(target_trainer.pokemon)} Pokemon")
                for pokemon in target_trainer.pokemon:
                    species = pokemon.get('species', 'Unknown')
                    level = pokemon.get('level', '?')
                    poke_type = pokemon.get('type', '')
                    type_info = f" ({poke_type})" if poke_type else ""
                    lines.append(f"  • {species}{type_info} - Level {level}")

            if target_trainer.prize_money:
                lines.append(f"PRIZE: ${target_trainer.prize_money}")

            lines.append("")

            # Add relevant tips
            if knowledge['tips']:
                lines.append("STRATEGY TIPS:")
                for tip in knowledge['tips']:
                    if any(keyword in tip.lower() for keyword in ['battle', 'use', 'effective', 'weak', 'strong']):
                        lines.append(f"  • {tip.strip()}")

        return "\n".join(lines)

    def get_next_steps(
        self,
        milestone_id: str,
        location: str
    ) -> List[str]:
        """
        Get recommended next steps for current state.

        Args:
            milestone_id: Current milestone
            location: Current location

        Returns:
            List of next step strings
        """
        knowledge = self.get_contextual_knowledge(milestone_id, location)

        if not knowledge['current_section']:
            return []

        section = knowledge['current_section']

        # Return objectives as next steps
        return section.objectives[:5]  # Top 5 next steps

    def get_items_to_collect(
        self,
        milestone_id: str,
        location: str,
        exclude_hidden: bool = False
    ) -> List[str]:
        """
        Get list of items available in current area.

        Args:
            milestone_id: Current milestone
            location: Current location
            exclude_hidden: If True, exclude hidden items

        Returns:
            List of item descriptions
        """
        knowledge = self.get_contextual_knowledge(milestone_id, location)

        items = []
        for item in knowledge['items_available']:
            if exclude_hidden and item.is_hidden:
                continue

            items.append(f"{item.name} - {item.location_detail}")

        return items

    def get_available_sections(self) -> Dict[str, KnowledgeSection]:
        """Get all available knowledge sections"""
        return self.sections.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        map_stats = self.map_provider.get_cache_stats()

        total_trainers = sum(len(s.trainers) for s in self.sections.values())
        total_items = sum(len(s.items) for s in self.sections.values())
        total_pokemon = sum(len(s.available_pokemon) for s in self.sections.values())
        total_tips = sum(len(s.tips) for s in self.sections.values())

        return {
            'knowledge_sections': len(self.sections),
            'total_maps': map_stats['total_maps'],
            'location_mappings': map_stats['location_mappings'],
            'total_trainers': total_trainers,
            'total_items': total_items,
            'total_pokemon': total_pokemon,
            'total_tips': total_tips,
        }

    def preload_resources(self):
        """Preload all maps for better performance"""
        logger.info("Preloading all knowledge resources...")
        self.map_provider.preload_all_maps()
        logger.info("Resources preloaded successfully")

    def clear_cache(self):
        """Clear cached resources to free memory"""
        self.map_provider.clear_cache()
        logger.info("Knowledge cache cleared")

    def __repr__(self):
        return (
            f"KnowledgeManager("
            f"sections={len(self.sections)}, "
            f"maps={self.map_provider.get_cache_stats()['total_maps']}"
            f")"
        )
