# Knowledge Base Implementation Plan
## Speedrun.md Integration with Simple Agent for First Gym Completion

**Created:** 2025-11-12
**Objective:** Integrate speedrun.md walkthrough knowledge and map .png files into the simple agent to provide context-aware guidance from game start through defeating Roxanne (first gym).

---

## Executive Summary

This plan outlines a comprehensive system to transform the static speedrun.md walkthrough into an **active knowledge base** that the agent can query and utilize based on its current milestone and location. The system will:

1. **Parse speedrun.md** into structured, queryable knowledge chunks
2. **Map milestones** to relevant speedrun sections
3. **Inject contextual knowledge** into VLM prompts based on current game state
4. **Provide map images** as additional visual context to the VLM
5. **Enable dynamic guidance** that adapts as the agent progresses

---

## Current State Analysis

### Existing Components

#### 1. Milestone System (simple.py lines 245-426)
- **26 storyline objectives** from GAME_RUNNING → FIRST_GYM_COMPLETE
- Each milestone has: id, description, type, target_value, milestone_id
- Milestones are auto-verified by emulator state
- **Gap:** No connection to speedrun knowledge

#### 2. SpeedrunRouter (utils/speedrun_router.py)
- **20 checkpoints** (cp_000 to cp_019) matching milestones
- Includes: optimal actions, recommended teams, key items, notes
- Has progress tracking and efficiency rating
- **Gap:** Basic notes, no detailed walkthroughs

#### 3. VLM Prompt System (simple.py lines 1733-1856)
- Uses get_full_prompt() or get_compact_prompt()
- Includes: context, history, objectives, formatted state, battle analysis
- Already integrates: movement memory, strategic memory, speedrun progress, collision warnings
- **Gap:** No integration of detailed speedrun knowledge or map images

#### 4. Available Resources
- **speedrun.md:** Comprehensive walkthrough with:
  - Location descriptions
  - Trainer battles with levels/moves
  - Available Pokemon and items
  - Step-by-step guidance
  - Pro tips and strategies

- **Map Images (data/knowledge/):**
  - Littleroot_Town_E.png
  - Hoenn_Route_101_E.png
  - Hoenn_Route_103_E.png
  - Oldale_Town_E.png
  - Hoenn_Route_104_E.png
  - Rustboro_City_E.png
  - Rustboro_Gym_E.png

---

## Architecture Design

### Component 1: Knowledge Parser (New File)
**File:** `utils/knowledge_parser.py`

**Purpose:** Parse speedrun.md into structured, queryable knowledge chunks

**Structure:**
```python
@dataclass
class KnowledgeSection:
    """A section of speedrun knowledge"""
    section_id: str              # "littleroot_town", "route_101", etc.
    title: str                   # "Littleroot Town"
    location_id: str             # Maps to game location names
    content: str                 # Full markdown content
    objectives: List[str]        # Key objectives in this section
    trainers: List[Dict]         # Trainer battles with details
    available_pokemon: List[Dict]# Wild Pokemon encounters
    items: List[Dict]            # Items available here
    tips: List[str]              # Strategic tips/notes
    prerequisites: List[str]     # Previous sections needed
    next_sections: List[str]     # Possible next sections
    milestone_ids: List[str]     # Related milestone IDs

class KnowledgeParser:
    def __init__(self, knowledge_file: str):
        """Load and parse speedrun.md"""

    def parse_markdown(self) -> Dict[str, KnowledgeSection]:
        """Parse markdown into structured sections"""

    def get_section_by_location(self, location: str) -> Optional[KnowledgeSection]:
        """Get knowledge for a specific location"""

    def get_section_by_milestone(self, milestone_id: str) -> Optional[KnowledgeSection]:
        """Get knowledge for a specific milestone"""

    def get_relevant_sections(self, current_milestone: str, context: str) -> List[KnowledgeSection]:
        """Get all relevant sections for current state"""
```

**Implementation Steps:**
1. Parse markdown by headers (# Introduction, # Littleroot Town, etc.)
2. Extract structured data from each section:
   - Items (look for "## Items" headers)
   - Trainers (look for battle info with Pokemon/levels)
   - Available Pokemon (look for encounter tables)
   - Tips (extract from narrative text)
3. Create milestone-to-section mapping
4. Build location-to-section index

---

### Component 2: Map Provider (New File)
**File:** `utils/map_provider.py`

**Purpose:** Provide map images based on current location

**Structure:**
```python
@dataclass
class MapData:
    """Map image data with metadata"""
    location_name: str           # "Littleroot Town"
    image_path: str              # Path to .png file
    image: Image.Image           # Loaded PIL image
    map_bank: Optional[int]      # Game map bank (if known)
    map_number: Optional[int]    # Game map number (if known)
    description: str             # Brief description

class MapProvider:
    def __init__(self, maps_directory: str = "data/knowledge"):
        """Initialize with maps directory"""
        self._load_available_maps()

    def _load_available_maps(self):
        """Scan directory and index all map images"""

    def get_map_for_location(self, location: str) -> Optional[MapData]:
        """Get map image for a location"""

    def get_map_for_milestone(self, milestone_id: str) -> Optional[MapData]:
        """Get map image for a milestone"""

    def get_map_by_coords(self, map_bank: int, map_number: int) -> Optional[MapData]:
        """Get map by game coordinates"""
```

**Location Mapping:**
```python
LOCATION_TO_MAP = {
    "LITTLEROOT_TOWN": "Littleroot_Town_E.png",
    "ROUTE101": "Hoenn_Route_101_E.png",
    "ROUTE103": "Hoenn_Route_103_E.png",
    "OLDALE_TOWN": "Oldale_Town_E.png",
    "ROUTE104": "Hoenn_Route_104_E.png",
    "RUSTBORO_CITY": "Rustboro_City_E.png",
    "RUSTBORO_CITY_GYM": "Rustboro_Gym_E.png",
}
```

---

### Component 3: Knowledge Manager (New File)
**File:** `utils/knowledge_manager.py`

**Purpose:** Central orchestrator that combines knowledge parser and map provider

**Structure:**
```python
class KnowledgeManager:
    """Manages knowledge base and provides context-aware information"""

    def __init__(self,
                 knowledge_file: str = "data/knowledge/speedrun.md",
                 maps_directory: str = "data/knowledge"):
        self.parser = KnowledgeParser(knowledge_file)
        self.map_provider = MapProvider(maps_directory)
        self.sections = self.parser.parse_markdown()

    def get_contextual_knowledge(self,
                                 milestone_id: str,
                                 location: str,
                                 context: str) -> Dict[str, Any]:
        """
        Get all relevant knowledge for current state.

        Returns:
            {
                'current_section': KnowledgeSection,
                'map_image': Image.Image or None,
                'formatted_guidance': str,
                'objectives': List[str],
                'tips': List[str],
                'trainers_ahead': List[Dict],
                'items_available': List[Dict]
            }
        """

    def format_knowledge_for_prompt(self,
                                    milestone_id: str,
                                    location: str,
                                    context: str,
                                    include_full_details: bool = True) -> str:
        """
        Format knowledge as text to inject into VLM prompt.

        Returns formatted string with:
        - Current location overview
        - Key objectives
        - Available items/Pokemon
        - Upcoming trainers
        - Strategic tips
        """

    def get_map_image(self,
                     milestone_id: str,
                     location: str) -> Optional[Image.Image]:
        """Get map image for current location"""
```

**Example Output Format:**
```
📚 SPEEDRUN KNOWLEDGE - LITTLEROOT TOWN:

LOCATION: Littleroot Town
DESCRIPTION: Quaint town on the southern edge of Hoenn. Contains your home,
Professor Birch's home, and Birch's Pokemon Laboratory.

KEY OBJECTIVES:
✓ Visit neighbor's house and meet May/Brendan
✓ Travel north to Route 101 to save Professor Birch
✓ Choose starter Pokemon (Mudkip recommended for speedruns)
✓ Return to Birch's Lab to receive Pokedex

ITEMS AVAILABLE:
- Potion (in PC in player's room)

NEXT STEPS:
1. Exit your house after setting the clock
2. Visit Professor Birch's house (next door)
3. Go upstairs to meet May/Brendan
4. Head north to Route 101

💡 SPEEDRUN TIPS:
- Mudkip is optimal starter (strong vs Roxanne's Rock types)
- Skip unnecessary dialogue by pressing A rapidly
- Don't catch extra Pokemon yet - focus on progression
```

---

### Component 4: Integration into SimpleAgent

**File:** `agent/simple.py` (modifications)

#### Changes to __init__:
```python
class SimpleAgent:
    def __init__(self, vlm, ...):
        # ... existing initialization ...

        # NEW: Initialize knowledge manager
        self.knowledge_manager = KnowledgeManager(
            knowledge_file="data/knowledge/speedrun.md",
            maps_directory="data/knowledge"
        )
        logger.info("Knowledge Manager initialized with speedrun guide and map images")
```

#### Changes to process_step (around line 1800):
```python
def process_step(self, frame, game_state: Dict[str, Any]) -> str:
    # ... existing code ...

    # NEW: Get contextual knowledge based on current milestone/location
    current_milestone = self._get_current_milestone(game_state)
    location = game_state.get("player", {}).get("location", "")

    knowledge_guidance = ""
    map_image = None

    if current_milestone and location:
        try:
            # Get formatted knowledge for prompt
            knowledge_guidance = self.knowledge_manager.format_knowledge_for_prompt(
                milestone_id=current_milestone,
                location=location,
                context=context,
                include_full_details=(not use_compact_prompt)
            )

            # Get map image for multi-image VLM call
            map_image = self.knowledge_manager.get_map_image(
                milestone_id=current_milestone,
                location=location
            )

            logger.info(f"📚 Injecting speedrun knowledge for {location}")
            if map_image:
                logger.info(f"🗺️  Adding overview map image as visual context")

        except Exception as e:
            logger.warning(f"Failed to retrieve knowledge: {e}")

    # ... continue with existing prompt building ...

    # MODIFIED: Inject knowledge guidance into prompt
    if knowledge_guidance:
        # Add knowledge section to prompt
        prompt = prompt + "\n\n" + knowledge_guidance

    # MODIFIED: Make VLM call with multiple images if map available
    if map_image:
        # Multi-image call: [game_screenshot, overview_map]
        response = self.vlm.get_query_multi_image(
            images=[frame, map_image],
            text=prompt,
            module_name="simple_mode_with_map"
        )
    else:
        # Single image call (existing behavior)
        response = self.vlm.get_query(frame, prompt, "simple_mode")
```

#### New Helper Method:
```python
def _get_current_milestone(self, game_state: Dict[str, Any]) -> Optional[str]:
    """
    Determine current active milestone based on game state.

    Returns milestone_id of the current/next incomplete storyline objective.
    """
    for objective in self.state.objectives:
        if objective.storyline and not objective.completed:
            return objective.milestone_id
    return None
```

---

### Component 5: VLM Backend Enhancement

**File:** `utils/vlm.py` (modifications)

Add multi-image support to VLM backends:

```python
class VLMBackend:
    @abstractmethod
    def get_query_multi_image(self,
                             images: List[Image.Image],
                             text: str,
                             module_name: str) -> str:
        """
        Query VLM with multiple images.

        Args:
            images: List of PIL Images (e.g., [game_frame, overview_map])
            text: Prompt text
            module_name: Module identifier for logging

        Returns:
            VLM response text
        """
        pass
```

**Implementation for each backend:**

1. **Gemini:** Already supports multi-image natively
2. **OpenAI GPT-4o:** Supports multiple image_url entries
3. **OpenRouter:** Depends on model, but most support it
4. **Local models:** May need to concatenate images side-by-side

---

## Detailed Milestone-to-Knowledge Mapping

| Milestone ID | Knowledge Section(s) | Map Image | Key Guidance |
|--------------|---------------------|-----------|--------------|
| GAME_RUNNING | Introduction | - | Press A to skip intro |
| INTRO_CUTSCENE_COMPLETE | Home | Littleroot_Town_E.png | Exit moving van by going RIGHT |
| PLAYER_HOUSE_ENTERED | Home | Littleroot_Town_E.png | Go upstairs to bedroom |
| PLAYER_BEDROOM | Home | Littleroot_Town_E.png | Set clock, then go downstairs |
| CLOCK_SET | Littleroot Town | Littleroot_Town_E.png | Visit neighbor's house next door |
| RIVAL_HOUSE | Professor Birch's House | Littleroot_Town_E.png | Go upstairs to meet May/Brendan |
| RIVAL_BEDROOM | Professor Birch's House | Littleroot_Town_E.png | Meet rival, then head to Route 101 |
| ROUTE_101 | Route 101 | Hoenn_Route_101_E.png | Save Birch from Zigzagoon, choose starter |
| STARTER_CHOSEN | Route 101 (Starter Choice) | Hoenn_Route_101_E.png | Choose Mudkip (optimal for speedrun) |
| BIRCH_LAB_VISITED | Littleroot Town (Birch's Lab) | Littleroot_Town_E.png | Receive Pokedex and Pokeballs |
| OLDALE_TOWN | Oldale Town | Oldale_Town_E.png | Get free Potion from Mart worker |
| ROUTE_103 | Route 103 | Hoenn_Route_103_E.png | Battle rival (optional) |
| RECEIVED_POKEDEX | Littleroot Town | Littleroot_Town_E.png | Mom gives Running Shoes |
| ROUTE_102 | Route 102 | - | Head west to Petalburg City |
| PETALBURG_CITY | Petalburg City | - | Visit Dad's gym |
| DAD_FIRST_MEETING | Petalburg City (Gym) | - | Help Wally catch Pokemon |
| ROUTE_104_SOUTH | Route 104 | Hoenn_Route_104_E.png | Catch Marill (useful for HMs) |
| PETALBURG_WOODS | Petalburg Woods | - | Battle Team Aqua Grunt |
| TEAM_AQUA_GRUNT_DEFEATED | Petalburg Woods | - | Receive Great Ball, continue north |
| ROUTE_104_NORTH | Route 104 | Hoenn_Route_104_E.png | Get Wailmer Pail from Flower Shop |
| RUSTBORO_CITY | Rustboro City | Rustboro_City_E.png | Get HM01 Cut from Cutter's house |
| RUSTBORO_GYM_ENTERED | Rustboro Gym | Rustboro_Gym_E.png | Challenge Roxanne (Rock-type gym) |
| ROXANNE_DEFEATED | Rustboro Gym | Rustboro_Gym_E.png | Water Gun is super effective |
| FIRST_GYM_COMPLETE | Rustboro City | Rustboro_City_E.png | Receive Stone Badge and TM39 |

---

## Implementation Phases

### Phase 1: Knowledge Parser (2-3 hours)
**Files to create:**
- `utils/knowledge_parser.py`

**Tasks:**
1. Create KnowledgeSection dataclass
2. Implement markdown parsing logic
3. Extract sections by headers
4. Parse trainer battles (look for "**Name**" patterns)
5. Parse items (look for bullet lists under "## Items")
6. Parse Pokemon encounters (look for level ranges and percentages)
7. Create milestone-to-section mapping table
8. Write unit tests

**Validation:**
```python
# Test that we can parse all sections
parser = KnowledgeParser("data/knowledge/speedrun.md")
sections = parser.parse_markdown()
assert len(sections) >= 15  # At least 15 locations
assert "littleroot_town" in sections
assert sections["littleroot_town"].trainers == []
assert len(sections["route_101"].available_pokemon) > 0
```

### Phase 2: Map Provider (1-2 hours)
**Files to create:**
- `utils/map_provider.py`

**Tasks:**
1. Create MapData dataclass
2. Scan data/knowledge/ for .png files
3. Build location-to-filename mapping
4. Implement lazy image loading (load on demand)
5. Add caching for loaded images
6. Write unit tests

**Validation:**
```python
# Test that we can load all maps
provider = MapProvider("data/knowledge")
map_data = provider.get_map_for_location("LITTLEROOT_TOWN")
assert map_data is not None
assert map_data.image.size[0] > 0
```

### Phase 3: Knowledge Manager (2-3 hours)
**Files to create:**
- `utils/knowledge_manager.py`

**Tasks:**
1. Create KnowledgeManager class
2. Implement get_contextual_knowledge()
3. Implement format_knowledge_for_prompt()
4. Create compact vs full formatting modes
5. Add integration with SpeedrunRouter for checkpoint sync
6. Write comprehensive unit tests

**Validation:**
```python
# Test end-to-end knowledge retrieval
manager = KnowledgeManager()
knowledge = manager.get_contextual_knowledge(
    milestone_id="ROUTE_101",
    location="ROUTE101",
    context="overworld"
)
assert knowledge['current_section'] is not None
assert knowledge['map_image'] is not None
assert len(knowledge['tips']) > 0
```

### Phase 4: VLM Multi-Image Support (2-3 hours)
**Files to modify:**
- `utils/vlm.py`

**Tasks:**
1. Add get_query_multi_image() abstract method
2. Implement for GeminiBackend (native support)
3. Implement for OpenAIBackend (multiple image_url)
4. Implement for OpenRouterBackend
5. Implement for LocalBackend (concatenate images)
6. Add fallback to single-image if multi not supported
7. Update llm_logger to log multi-image calls

**Example Implementation (Gemini):**
```python
def get_query_multi_image(self, images: List[Image.Image], text: str, module_name: str) -> str:
    """Gemini natively supports multiple images"""
    try:
        # Convert all images
        image_parts = [{"mime_type": "image/png", "data": self._encode_image(img)}
                      for img in images]

        contents = image_parts + [{"text": text}]

        response = self.model.generate_content(contents)
        return response.text

    except Exception as e:
        logger.error(f"Multi-image query failed: {e}")
        # Fallback to first image only
        return self.get_query(images[0], text, module_name)
```

### Phase 5: SimpleAgent Integration (3-4 hours)
**Files to modify:**
- `agent/simple.py`

**Tasks:**
1. Add knowledge_manager to __init__
2. Add _get_current_milestone() helper
3. Modify process_step() to retrieve knowledge
4. Inject knowledge into prompt building
5. Add multi-image VLM call logic
6. Add configuration flags (enable/disable knowledge, enable/disable maps)
7. Update logging to show when knowledge is used
8. Test with actual game runs

**Configuration:**
```python
# Environment variables for control
ENABLE_KNOWLEDGE_BASE = os.getenv('ENABLE_KNOWLEDGE_BASE', 'true').lower() == 'true'
ENABLE_MAP_IMAGES = os.getenv('ENABLE_MAP_IMAGES', 'true').lower() == 'true'
KNOWLEDGE_DETAIL_LEVEL = os.getenv('KNOWLEDGE_DETAIL_LEVEL', 'full')  # 'full', 'compact', 'minimal'
```

### Phase 6: Testing & Refinement (2-3 hours)
**Tasks:**
1. Run complete playthrough from start to first gym
2. Monitor VLM prompts for quality
3. Verify knowledge is relevant at each milestone
4. Check map images are correctly matched
5. Measure impact on decision quality
6. Optimize prompt length if needed
7. Add edge case handling (missing knowledge, corrupted maps, etc.)

---

## Prompt Format Example

**With Knowledge Base Enabled:**

```
🎮 GAME STATE:
Location: ROUTE101
Coordinates: (8, 12)
Context: overworld
Party: Mudkip (Lv 5) - HP: 22/22

📚 SPEEDRUN KNOWLEDGE - ROUTE 101:

LOCATION: Route 101
DESCRIPTION: Short path connecting Littleroot Town to Oldale Town. Features
several patches of tall grass where wild Pokemon hide.

CURRENT OBJECTIVE: Save Professor Birch from wild Zigzagoon!
Professor Birch is being chased by a wild Zigzagoon. His bag has fallen nearby.
Choose one of three starter Pokemon from the bag to help scare off the attacker.

STARTER CHOICE - RECOMMENDED FOR SPEEDRUN:
✅ MUDKIP (Water type) - BEST CHOICE
   - Evolves into Marshtomp (Water/Ground) at Lv 16
   - Evolves into Swampert (Water/Ground) at Lv 36
   - Strong against Roxanne (Rock), Flannery (Fire)
   - Only weak to Grass (uncommon in Emerald)
   - Learns Surf early (best Water move)

Other Starters:
- Treecko (Grass): Good, but struggles with many gyms
- Torchic (Fire/Fighting): Decent, but weak to common Water types

WILD POKEMON ENCOUNTERS (after getting starter):
- Poochyena (Level 2-3) - 45% encounter rate
- Wurmple (Level 2-3) - 45% encounter rate
- Zigzagoon (Level 2-3) - 10% encounter rate

💡 SPEEDRUN TIPS:
- Choose Mudkip for optimal gym coverage
- Don't catch extra Pokemon yet - wastes time
- Avoid wild battles when possible
- After saving Birch, return to his lab in Littleroot

NEXT STEPS:
1. Save Professor Birch by choosing a starter
2. Battle the wild Zigzagoon (cannot catch it)
3. Return to Littleroot Town
4. Visit Birch's Lab to keep your starter permanently

🗺️ OVERVIEW MAP: [Second image shows full Route 101 layout]

[Rest of standard prompt: objectives, recent actions, movement preview, etc.]
```

---

## Success Metrics

### Quantitative Metrics:
1. **Milestone Completion Time:** Measure time to reach each milestone
2. **Action Efficiency:** Compare actions taken vs optimal speedrun route
3. **Stuck Frequency:** Track how often agent gets stuck (should decrease)
4. **Trainer Battle Win Rate:** Track first-attempt battle wins
5. **Wrong-Way Navigation:** Track backtracking incidents

### Qualitative Metrics:
1. **Decision Quality:** Agent makes more informed choices
2. **Strategic Awareness:** Agent understands gym type matchups
3. **Resource Management:** Agent collects important items
4. **Objective Focus:** Agent stays on critical path

### Target Improvements:
- **15-25% faster** milestone completion
- **30-40% fewer** stuck incidents
- **50%+ reduction** in wrong-way navigation
- **Near-perfect** starter choice (Mudkip for speedruns)
- **100%** first-gym win rate with proper preparation

---

## Configuration & Toggles

Add to environment variables or config:

```bash
# Enable/disable knowledge base
export ENABLE_KNOWLEDGE_BASE=true

# Enable/disable map images (saves tokens if disabled)
export ENABLE_MAP_IMAGES=true

# Knowledge detail level: full, compact, minimal
export KNOWLEDGE_DETAIL_LEVEL=full

# Map image resolution (resize if needed to save tokens)
export MAP_IMAGE_MAX_SIZE=800

# Knowledge injection mode: prompt, system, both
export KNOWLEDGE_INJECTION_MODE=prompt
```

---

## Risks & Mitigations

### Risk 1: Token Limit Exceeded
**Mitigation:**
- Implement dynamic knowledge truncation
- Use compact mode for local models
- Prioritize most relevant sections only

### Risk 2: Map Images Too Large
**Mitigation:**
- Resize maps to max 800x800
- Use JPEG instead of PNG for compression
- Make map images optional (env var)

### Risk 3: Knowledge Becomes Outdated
**Mitigation:**
- Version speedrun.md
- Add validation to detect missing sections
- Graceful degradation if knowledge unavailable

### Risk 4: Wrong Knowledge for State
**Mitigation:**
- Robust milestone-to-section mapping
- Fallback to nearby sections if exact match missing
- Log all knowledge retrievals for debugging

### Risk 5: VLM Ignores Knowledge
**Mitigation:**
- Use attention-grabbing formatting (emojis, headers)
- Place knowledge early in prompt
- Test with different VLM models
- Use explicit instructions to reference the knowledge

---

## Testing Strategy

### Unit Tests:
```python
# test_knowledge_parser.py
def test_parse_all_sections()
def test_extract_trainers()
def test_extract_items()
def test_milestone_mapping()

# test_map_provider.py
def test_load_all_maps()
def test_location_mapping()
def test_image_caching()

# test_knowledge_manager.py
def test_contextual_knowledge()
def test_prompt_formatting()
def test_multi_image_assembly()
```

### Integration Tests:
```python
# test_agent_knowledge_integration.py
def test_knowledge_injected_in_prompt()
def test_map_images_sent_to_vlm()
def test_milestone_progression_updates_knowledge()
def test_graceful_degradation()
```

### End-to-End Tests:
1. Run agent from game start with knowledge enabled
2. Verify correct knowledge at each milestone
3. Confirm map images loaded correctly
4. Check VLM receives both game frame and map
5. Measure completion time vs baseline

---

## Future Enhancements

### Post-First-Gym Features:
1. **Expand to All 8 Gyms:** Parse rest of speedrun guide
2. **Item Database:** Add detailed item effects/locations
3. **Pokemon Database:** Add type charts, move effectiveness
4. **Battle Strategy Knowledge:** Detailed trainer battle tactics
5. **Speedrun Leaderboard:** Track best times per segment
6. **Knowledge Learning:** Agent learns from mistakes, updates knowledge
7. **Multi-Language Support:** Translate knowledge for different ROM versions

### Advanced Features:
1. **Dynamic Knowledge Updates:** Agent can add notes to knowledge base
2. **Crowd-Sourced Knowledge:** Community contributes tips
3. **Visual Knowledge:** Extract info from map images using CV
4. **Knowledge Graph:** Represent locations/items/trainers as graph
5. **Adaptive Difficulty:** Adjust knowledge detail based on agent performance

---

## Implementation Timeline

**Total Estimated Time: 12-18 hours**

- **Day 1 (6-8 hours):** Phases 1-3 (Parser, Provider, Manager)
- **Day 2 (4-6 hours):** Phases 4-5 (VLM enhancement, Integration)
- **Day 3 (2-4 hours):** Phase 6 (Testing, refinement, documentation)

**Parallel Work Opportunities:**
- Knowledge parser and map provider can be developed simultaneously
- VLM backend work can start before knowledge manager is complete
- Testing can begin as soon as Phase 5 integration is functional

---

## Conclusion

This knowledge base system will transform the simple agent from a **reactive explorer** into a **goal-oriented speedrunner** by providing:

1. **Strategic Context:** Knows what's ahead and can plan accordingly
2. **Visual Overview:** Sees both immediate surroundings and full map layout
3. **Expert Guidance:** Follows proven speedrun strategies
4. **Informed Decisions:** Makes choices based on comprehensive knowledge

**Expected Impact:**
- Significantly faster first gym completion
- Fewer stuck situations and backtracking
- Better Pokemon team composition
- More efficient resource collection
- Higher success rate on first attempts

The modular design ensures easy extension to cover the entire game, while configuration flags allow fine-tuning for different VLM backends and use cases.
