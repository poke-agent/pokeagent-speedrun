"""
Knowledge Parser for Pokemon Emerald Speedrun Guide

Parses speedrun.md into structured, queryable knowledge chunks.
Each section represents a location or milestone with detailed information.

Part of the Knowledge Base Implementation Plan - Phase 1
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TrainerInfo:
    """Information about a trainer battle"""
    name: str
    trainer_class: str  # "Youngster", "Bug Catcher", "Gym Leader", etc.
    pokemon: List[Dict[str, Any]]  # List of Pokemon with level, moves, etc.
    prize_money: Optional[int] = None
    notes: str = ""


@dataclass
class PokemonEncounter:
    """Wild Pokemon encounter information"""
    species: str
    level_range: str  # "2-3", "5", etc.
    encounter_rate: str  # "45%", "rare", etc.
    location_detail: Optional[str] = None  # "in tall grass", "surfing", etc.


@dataclass
class ItemInfo:
    """Information about an item"""
    name: str
    location_detail: str
    is_hidden: bool = False
    requires_hm: Optional[str] = None  # "Cut", "Surf", etc.


@dataclass
class KnowledgeSection:
    """A section of speedrun knowledge representing a location or milestone"""
    section_id: str              # "littleroot_town", "route_101", etc.
    title: str                   # "Littleroot Town", "Route 101"
    location_id: str             # Maps to game location names (LITTLEROOT_TOWN, ROUTE101)
    content: str                 # Full markdown content
    description: str = ""        # Brief description of the location
    objectives: List[str] = field(default_factory=list)  # Key objectives
    trainers: List[TrainerInfo] = field(default_factory=list)  # Trainer battles
    available_pokemon: List[PokemonEncounter] = field(default_factory=list)  # Wild Pokemon
    items: List[ItemInfo] = field(default_factory=list)  # Items available
    tips: List[str] = field(default_factory=list)  # Strategic tips/notes
    prerequisites: List[str] = field(default_factory=list)  # Previous sections needed
    next_sections: List[str] = field(default_factory=list)  # Possible next sections
    milestone_ids: List[str] = field(default_factory=list)  # Related milestone IDs
    subsections: Dict[str, str] = field(default_factory=dict)  # Subsections by header


class KnowledgeParser:
    """
    Parses speedrun.md markdown file into structured knowledge sections.

    Each location/area in the guide becomes a KnowledgeSection with
    extracted trainers, items, Pokemon, tips, and objectives.
    """

    def __init__(self, knowledge_file: str = "data/knowledge/speedrun.md"):
        """
        Initialize the knowledge parser.

        Args:
            knowledge_file: Path to speedrun.md file
        """
        self.knowledge_file = Path(knowledge_file)
        self.sections: Dict[str, KnowledgeSection] = {}
        self.raw_content: str = ""

        # Mapping of section titles to game location IDs
        self.location_mapping = {
            "Introduction": "INTRO",
            "Home": "MOVING_VAN",
            "Littleroot Town": "LITTLEROOT_TOWN",
            "Route 101": "ROUTE101",
            "Oldale Town": "OLDALE_TOWN",
            "Route 103": "ROUTE103",
            "Route 102": "ROUTE102",
            "Petalburg City": "PETALBURG_CITY",
            "Petalburg City (first visit)": "PETALBURG_CITY",
            "Route 104": "ROUTE104",
            "Route 104 (south)": "ROUTE104",
            "Route 104 (north)": "ROUTE104",
            "Petalburg Woods": "PETALBURG_WOODS",
            "Rustboro City": "RUSTBORO_CITY",
            "Rustboro Gym": "RUSTBORO_CITY_GYM",
        }

        # Important subsections to promote to full sections (gyms, labs, etc.)
        self.important_subsections = [
            "Rustboro Gym",
            "Professor Birch's House",
            "Birch's Lab",
            "Pretty Petal Flower Shop",
            "Petalburg Gym"
        ]

        # Milestone mapping
        self.milestone_mapping = {
            "INTRO": ["GAME_RUNNING", "INTRO_CUTSCENE_COMPLETE"],
            "MOVING_VAN": ["INTRO_CUTSCENE_COMPLETE", "PLAYER_HOUSE_ENTERED"],
            "LITTLEROOT_TOWN": ["PLAYER_HOUSE_ENTERED", "PLAYER_BEDROOM", "CLOCK_SET",
                               "RIVAL_HOUSE", "RIVAL_BEDROOM", "BIRCH_LAB_VISITED", "RECEIVED_POKEDEX"],
            "ROUTE101": ["ROUTE_101", "STARTER_CHOSEN"],
            "OLDALE_TOWN": ["OLDALE_TOWN"],
            "ROUTE103": ["ROUTE_103"],
            "ROUTE102": ["ROUTE_102"],
            "PETALBURG_CITY": ["PETALBURG_CITY", "DAD_FIRST_MEETING", "GYM_EXPLANATION"],
            "ROUTE104": ["ROUTE_104_SOUTH", "ROUTE_104_NORTH"],
            "PETALBURG_WOODS": ["PETALBURG_WOODS", "TEAM_AQUA_GRUNT_DEFEATED"],
            "RUSTBORO_CITY": ["RUSTBORO_CITY"],
            "RUSTBORO_CITY_GYM": ["RUSTBORO_GYM_ENTERED", "ROXANNE_DEFEATED", "FIRST_GYM_COMPLETE"],
        }

        logger.info(f"Initialized KnowledgeParser with file: {self.knowledge_file}")

    def parse_markdown(self) -> Dict[str, KnowledgeSection]:
        """
        Parse the entire markdown file into structured sections.

        Returns:
            Dictionary mapping section_id -> KnowledgeSection
        """
        if not self.knowledge_file.exists():
            logger.error(f"Knowledge file not found: {self.knowledge_file}")
            return {}

        # Read entire file
        with open(self.knowledge_file, 'r', encoding='utf-8') as f:
            self.raw_content = f.read()

        logger.info(f"Read {len(self.raw_content)} characters from {self.knowledge_file}")

        # Split into sections by top-level headers (# Header)
        sections_raw = self._split_by_headers(self.raw_content)

        logger.info(f"Found {len(sections_raw)} top-level sections")

        # Parse each section
        for section_title, section_content in sections_raw.items():
            section = self._parse_section(section_title, section_content)
            if section:
                self.sections[section.section_id] = section

            # Also check for important subsections to promote
            subsections = self._parse_subsections(section_content)
            for subsection_title, subsection_content in subsections.items():
                if subsection_title in self.important_subsections:
                    # Create a full section from this subsection
                    subsection = self._parse_section(subsection_title, subsection_content, is_subsection=True)
                    if subsection:
                        self.sections[subsection.section_id] = subsection
                        logger.info(f"Promoted subsection to full section: {subsection_title}")

        # Build relationships between sections
        self._build_section_relationships()

        logger.info(f"Successfully parsed {len(self.sections)} knowledge sections")
        return self.sections

    def _split_by_headers(self, content: str) -> Dict[str, str]:
        """
        Split markdown content by top-level headers (# Header).

        Returns:
            Dictionary mapping header title -> section content
        """
        sections = {}
        current_title = None
        current_content = []

        for line in content.split('\n'):
            # Check if this is a top-level header (# Header)
            if line.startswith('# ') and not line.startswith('## '):
                # Save previous section
                if current_title:
                    sections[current_title] = '\n'.join(current_content)

                # Start new section
                current_title = line[2:].strip()
                current_content = []
            else:
                # Add to current section
                if current_title:
                    current_content.append(line)

        # Save last section
        if current_title:
            sections[current_title] = '\n'.join(current_content)

        return sections

    def _parse_section(self, title: str, content: str, is_subsection: bool = False) -> Optional[KnowledgeSection]:
        """
        Parse a single section into a KnowledgeSection object.

        Args:
            title: Section title (e.g., "Littleroot Town")
            content: Section markdown content
            is_subsection: True if this is a promoted subsection

        Returns:
            KnowledgeSection or None if parsing fails
        """
        try:
            # Generate section_id (lowercase, underscores)
            section_id = title.lower().replace(' ', '_').replace("'", "")

            # Get location ID from mapping
            location_id = self.location_mapping.get(title, section_id.upper())

            # Get milestone IDs
            milestone_ids = self.milestone_mapping.get(location_id, [])

            # Extract description (first paragraph)
            description = self._extract_description(content)

            # Parse subsections
            subsections = self._parse_subsections(content)

            # Extract trainers
            trainers = self._extract_trainers(content)

            # Extract Pokemon encounters
            pokemon = self._extract_pokemon(content)

            # Extract items
            items = self._extract_items(content)

            # Extract tips and objectives
            tips = self._extract_tips(content)
            objectives = self._extract_objectives(content, title)

            section = KnowledgeSection(
                section_id=section_id,
                title=title,
                location_id=location_id,
                content=content,
                description=description,
                objectives=objectives,
                trainers=trainers,
                available_pokemon=pokemon,
                items=items,
                tips=tips,
                milestone_ids=milestone_ids,
                subsections=subsections
            )

            logger.debug(f"Parsed section '{title}': {len(trainers)} trainers, "
                        f"{len(pokemon)} Pokemon, {len(items)} items, {len(tips)} tips")

            return section

        except Exception as e:
            logger.error(f"Error parsing section '{title}': {e}", exc_info=True)
            return None

    def _parse_subsections(self, content: str) -> Dict[str, str]:
        """Parse subsections (## Header) within a section"""
        subsections = {}
        current_header = None
        current_content = []

        for line in content.split('\n'):
            if line.startswith('## '):
                # Save previous subsection
                if current_header:
                    subsections[current_header] = '\n'.join(current_content).strip()

                # Start new subsection
                current_header = line[3:].strip()
                current_content = []
            else:
                if current_header:
                    current_content.append(line)

        # Save last subsection
        if current_header:
            subsections[current_header] = '\n'.join(current_content).strip()

        return subsections

    def _extract_description(self, content: str) -> str:
        """Extract the first paragraph as description"""
        lines = [l.strip() for l in content.split('\n') if l.strip()]

        # Find first non-header line
        for line in lines:
            if not line.startswith('#') and not line.startswith('-') and not line.startswith('*'):
                # Return first substantial paragraph (at least 20 chars)
                if len(line) >= 20:
                    return line

        return ""

    def _extract_trainers(self, content: str) -> List[TrainerInfo]:
        """
        Extract trainer battle information.

        Handles two formats:
        1. Inline: "- **Youngster Calvin** - Poochyena ♂, Level 5"
        2. Gym Leader: "### Gym Leader Roxanne" followed by Pokemon list
        """
        trainers = []
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i]

            # Format 1: Check for Gym Leader subsection header
            gym_leader_match = re.search(r'###\s*Gym\s*Leader\s+(\w+)', line, re.IGNORECASE)
            if gym_leader_match:
                trainer_name = gym_leader_match.group(1).strip()
                trainer_class = "Gym Leader"

                # Next lines should have prize money and Pokemon
                pokemon_list = []
                prize_money = None

                # Scan next ~20 lines for Pokemon and prize
                for j in range(i + 1, min(i + 20, len(lines))):
                    next_line = lines[j]

                    # Stop at next section
                    if next_line.startswith('#'):
                        break

                    # Check for prize money
                    prize_match = re.search(r'Prize:\s*(\d+)\s*Pokédollars', next_line)
                    if prize_match:
                        prize_money = int(prize_match.group(1))

                    # Check for Pokemon entries: "- **Species** (Type) ♀, Level 15"
                    poke_match = re.search(r'^\s*-\s*\*\*([A-Za-z]+)\*\*\s*\(([^)]+)\)[^,]*,\s*Level\s*(\d+)', next_line)
                    if poke_match:
                        species = poke_match.group(1).strip()
                        poke_type = poke_match.group(2).strip()
                        level = int(poke_match.group(3))

                        pokemon_list.append({
                            'species': species,
                            'type': poke_type,
                            'level': level,
                            'raw': next_line.strip()
                        })

                if pokemon_list:
                    trainer = TrainerInfo(
                        name=trainer_name,
                        trainer_class=trainer_class,
                        pokemon=pokemon_list,
                        prize_money=prize_money
                    )
                    trainers.append(trainer)
                    logger.debug(f"Found Gym Leader: {trainer_name} with {len(pokemon_list)} Pokemon")

                i += 1
                continue

            # Format 2: Inline trainer format
            trainer_match = re.search(r'\*\*([^*]+)\*\*\s*-\s*(.+)', line)
            if trainer_match:
                trainer_name = trainer_match.group(1).strip()
                pokemon_info = trainer_match.group(2).strip()

                # Extract trainer class if in parentheses
                class_match = re.search(r'\(([^)]+)\)', trainer_name)
                trainer_class = class_match.group(1) if class_match else "Trainer"
                trainer_name = re.sub(r'\s*\([^)]+\)', '', trainer_name).strip()

                # Parse Pokemon (simple parsing for now)
                pokemon_list = []
                for poke_entry in pokemon_info.split(';'):
                    poke_entry = poke_entry.strip()
                    if poke_entry:
                        # Try to extract species and level
                        level_match = re.search(r'Level?\s*(\d+)', poke_entry, re.IGNORECASE)
                        level = int(level_match.group(1)) if level_match else None

                        # Species is the first word(s) before level or comma
                        species = re.split(r'[,\(]', poke_entry)[0].strip()
                        species = re.sub(r'Level.*', '', species, flags=re.IGNORECASE).strip()
                        species = re.sub(r'[♂♀]', '', species).strip()

                        if species:
                            pokemon_list.append({
                                'species': species,
                                'level': level,
                                'raw': poke_entry
                            })

                # Extract prize money
                prize_match = re.search(r'(\d+)\s*Pokédollars', pokemon_info)
                prize_money = int(prize_match.group(1)) if prize_match else None

                # Skip invalid trainers (no Pokemon extracted)
                if not pokemon_list:
                    logger.debug(f"Skipping invalid trainer entry: {trainer_name}")
                    i += 1
                    continue

                trainer = TrainerInfo(
                    name=trainer_name,
                    trainer_class=trainer_class,
                    pokemon=pokemon_list,
                    prize_money=prize_money
                )
                trainers.append(trainer)

                logger.debug(f"Found trainer: {trainer_name} ({trainer_class}) with {len(pokemon_list)} Pokemon")

            i += 1

        return trainers

    def _extract_pokemon(self, content: str) -> List[PokemonEncounter]:
        """
        Extract wild Pokemon encounter information.

        Looks for patterns like:
        - **Poochyena** - Level 2-3 (45%)
        - Wurmple, Level 3-4 (30%)
        """
        pokemon = []

        # Look for "Available Pokemon" section
        if '## Available Pokémon' in content or '## Available Pokemon' in content:
            section_match = re.search(
                r'##\s*Available\s*Pok[eé]mon\s*\n(.*?)(?=\n##|\Z)',
                content,
                re.DOTALL | re.IGNORECASE
            )

            if section_match:
                pokemon_section = section_match.group(1)

                # Parse each line with Pokemon info
                for line in pokemon_section.split('\n'):
                    line = line.strip()

                    # Pattern: "- **Species** - Level X-Y (Z%)"
                    poke_match = re.search(
                        r'[-*]\s*\*?\*?([A-Za-z\s]+?)\*?\*?\s*[-–]\s*Level\s*([\d-]+)\s*\(([^)]+)\)',
                        line
                    )

                    if poke_match:
                        species = poke_match.group(1).strip()
                        level_range = poke_match.group(2).strip()
                        encounter_rate = poke_match.group(3).strip()

                        pokemon.append(PokemonEncounter(
                            species=species,
                            level_range=level_range,
                            encounter_rate=encounter_rate
                        ))

                        logger.debug(f"Found Pokemon: {species} (Lv {level_range}, {encounter_rate})")

        return pokemon

    def _extract_items(self, content: str) -> List[ItemInfo]:
        """
        Extract item information.

        Looks for patterns like:
        - **Potion** - From the PC in the player's room
        - Oran Berry ×2 - From the soft soil patch
        """
        items = []

        # Look for "Items" section (both ## and ###)
        if '## Items' in content or '### Items' in content:
            # Try ## first
            section_match = re.search(
                r'##\s*Items\s*\n(.*?)(?=\n##|\Z)',
                content,
                re.DOTALL
            )

            # Try ### if ## didn't work
            if not section_match:
                section_match = re.search(
                    r'###\s*Items\s*\n(.*?)(?=\n##|\Z)',
                    content,
                    re.DOTALL
                )

            if section_match:
                items_section = section_match.group(1)

                # Parse each item line
                for line in items_section.split('\n'):
                    line = line.strip()

                    # Pattern: "- **Item Name** - Location detail"
                    item_match = re.search(r'[-*]\s*\*?\*?([^*\n-]+?)\*?\*?\s*[-–]\s*(.+)', line)

                    if item_match:
                        item_name = item_match.group(1).strip()
                        location_detail = item_match.group(2).strip()

                        # Check if hidden
                        is_hidden = 'hidden' in location_detail.lower()

                        # Check if requires HM
                        requires_hm = None
                        for hm in ['Cut', 'Surf', 'Strength', 'Rock Smash', 'Fly', 'Waterfall', 'Dive']:
                            if hm in location_detail:
                                requires_hm = hm
                                break

                        items.append(ItemInfo(
                            name=item_name,
                            location_detail=location_detail,
                            is_hidden=is_hidden,
                            requires_hm=requires_hm
                        ))

                        logger.debug(f"Found item: {item_name} - {location_detail}")

        return items

    def _extract_tips(self, content: str) -> List[str]:
        """
        Extract strategic tips and important notes.

        Looks for standalone paragraphs that give advice or warnings.
        """
        tips = []

        # Common tip indicators
        tip_indicators = [
            'tip:', 'note:', 'important:', 'remember:', 'warning:',
            'recommended', 'optimal', 'should', 'must', 'avoid',
            'best choice', 'strategy', 'use', 'super effective',
            'weak', 'strong against', 'advise', 'suggest'
        ]

        lines = content.split('\n')
        for line in lines:
            line_lower = line.lower().strip()

            # Skip headers and empty lines
            if not line_lower or line.startswith('#'):
                continue

            # Skip lines that are just list markers
            if line_lower in ['-', '*', '•']:
                continue

            # Check if line contains tip indicators
            if any(indicator in line_lower for indicator in tip_indicators):
                # Clean up the line
                tip = line.strip('- *•').strip()
                if len(tip) >= 15:  # Substantial tip (lowered threshold)
                    tips.append(tip)

        return list(set(tips))  # Remove duplicates

    def _extract_objectives(self, content: str, title: str) -> List[str]:
        """
        Extract key objectives for this location.

        Looks for action-oriented statements and goals.
        """
        objectives = []

        # Look for subsection headers that indicate objectives
        objective_headers = [
            'Meet', 'Visit', 'Travel', 'Defeat', 'Obtain', 'Catch',
            'Battle', 'Challenge', 'Receive', 'Get', 'Find', 'Enter',
            'Go', 'Head', 'Navigate', 'Explore', 'Save', 'Help',
            'Return', 'Arrive'
        ]

        # Extract from subsection headers
        subsections = self._parse_subsections(content)
        for header in subsections.keys():
            if any(verb in header for verb in objective_headers):
                objectives.append(header)

        # Special case: Gym battles
        if 'Gym' in title:
            objectives.append(f"Challenge and defeat the {title} Leader")
            objectives.append(f"Earn badge from {title}")

        # Extract from descriptive paragraphs
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        for i, line in enumerate(lines[:20]):  # Check first 20 lines
            line_lower = line.lower()

            # Skip headers
            if line.startswith('#'):
                continue

            # Look for sentences with action verbs
            for verb in objective_headers:
                if verb.lower() in line_lower and len(line) < 150:
                    cleaned = line.strip('- *•.').strip()
                    if len(cleaned) >= 20:
                        objectives.append(cleaned)
                        break

        # Remove duplicates and limit
        objectives = list(dict.fromkeys(objectives))  # Preserve order while removing dupes
        return objectives[:8]  # Max 8 objectives

    def _build_section_relationships(self):
        """Build prerequisite and next_section relationships"""
        # Ordered list of sections in progression order
        progression_order = [
            'introduction', 'home', 'littleroot_town', 'route_101',
            'oldale_town', 'route_103', 'route_102', 'petalburg_city',
            'route_104', 'petalburg_woods', 'rustboro_city', 'rustboro_gym'
        ]

        for i, section_id in enumerate(progression_order):
            if section_id in self.sections:
                # Set prerequisites
                if i > 0:
                    self.sections[section_id].prerequisites = [progression_order[i-1]]

                # Set next sections
                if i < len(progression_order) - 1:
                    self.sections[section_id].next_sections = [progression_order[i+1]]

    def get_section_by_location(self, location: str) -> Optional[KnowledgeSection]:
        """
        Get knowledge section by game location name.

        Args:
            location: Game location ID (e.g., "LITTLEROOT_TOWN", "ROUTE101")

        Returns:
            KnowledgeSection or None
        """
        for section in self.sections.values():
            if section.location_id == location:
                return section
        return None

    def get_section_by_milestone(self, milestone_id: str) -> Optional[KnowledgeSection]:
        """
        Get knowledge section by milestone ID.

        Args:
            milestone_id: Milestone identifier (e.g., "STARTER_CHOSEN")

        Returns:
            KnowledgeSection or None
        """
        for section in self.sections.values():
            if milestone_id in section.milestone_ids:
                return section
        return None

    def get_relevant_sections(self,
                            current_milestone: str,
                            context: str = "overworld") -> List[KnowledgeSection]:
        """
        Get all relevant sections for current state.

        Args:
            current_milestone: Current milestone ID
            context: Game context (overworld, battle, dialogue, etc.)

        Returns:
            List of relevant KnowledgeSection objects
        """
        relevant = []

        # Get section for current milestone
        current_section = self.get_section_by_milestone(current_milestone)
        if current_section:
            relevant.append(current_section)

            # Also include next sections for forward-looking guidance
            for next_id in current_section.next_sections:
                if next_id in self.sections:
                    relevant.append(self.sections[next_id])

        return relevant

    def get_section_by_id(self, section_id: str) -> Optional[KnowledgeSection]:
        """Get section by its ID"""
        return self.sections.get(section_id)

    def get_all_sections(self) -> Dict[str, KnowledgeSection]:
        """Get all parsed sections"""
        return self.sections
