"""
Map Provider for Pokemon Emerald Knowledge Base

Provides map images based on current location for visual context.
Maps are full-area overviews that complement the game's limited viewport.

Part of the Knowledge Base Implementation Plan - Phase 2
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class MapData:
    """Map image data with metadata"""
    location_name: str           # "Littleroot Town"
    image_path: str              # Path to .png file
    image: Optional[Image.Image] = None  # Loaded PIL image (lazy loaded)
    map_bank: Optional[int] = None       # Game map bank (if known)
    map_number: Optional[int] = None     # Game map number (if known)
    description: str = ""                # Brief description


class MapProvider:
    """
    Provides map images for Pokemon Emerald locations.

    Maps are stored as .png files in data/knowledge/ directory and provide
    full-area overviews to complement the agent's limited viewport.
    Images are lazy-loaded and cached for performance.
    """

    def __init__(self, maps_directory: str = "data/knowledge"):
        """
        Initialize the map provider.

        Args:
            maps_directory: Directory containing map .png files
        """
        self.maps_directory = Path(maps_directory)
        self.maps: Dict[str, MapData] = {}
        self.location_to_map: Dict[str, str] = {}  # Location ID -> map key
        self._image_cache: Dict[str, Image.Image] = {}  # Cache loaded images

        # Location ID to filename mapping
        # Maps game location names to .png filenames
        self.location_mapping = {
            "LITTLEROOT_TOWN": "Littleroot_Town_E.png",
            "LITTLEROOT_TOWN_PLAYERS_HOUSE_1F": "Littleroot_Town_E.png",
            "LITTLEROOT_TOWN_PLAYERS_HOUSE_2F": "Littleroot_Town_E.png",
            "LITTLEROOT_TOWN_MAYS_HOUSE_1F": "Littleroot_Town_E.png",
            "LITTLEROOT_TOWN_MAYS_HOUSE_2F": "Littleroot_Town_E.png",
            "LITTLEROOT_TOWN_BRENDANS_HOUSE_1F": "Littleroot_Town_E.png",
            "LITTLEROOT_TOWN_BRENDANS_HOUSE_2F": "Littleroot_Town_E.png",
            "LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB": "Littleroot_Town_E.png",
            "ROUTE101": "Hoenn_Route_101_E.png",
            "ROUTE_101": "Hoenn_Route_101_E.png",
            "ROUTE103": "Hoenn_Route_103_E.png",
            "ROUTE_103": "Hoenn_Route_103_E.png",
            "OLDALE_TOWN": "Oldale_Town_E.png",
            "ROUTE104": "Hoenn_Route_104_E.png",
            "ROUTE_104": "Hoenn_Route_104_E.png",
            "ROUTE104_PROTOTYPE": "Hoenn_Route_104_E.png",
            "ROUTE104_PROTOTYPE_PRETTY_PETAL_FLOWER_SHOP": "Hoenn_Route_104_E.png",
            "RUSTBORO_CITY": "Rustboro_City_E.png",
            "RUSTBORO_CITY_POKEMON_CENTER_1F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_POKEMON_CENTER_2F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_POKEMON_SCHOOL": "Rustboro_City_E.png",
            "RUSTBORO_CITY_CUTTERS_HOUSE": "Rustboro_City_E.png",
            "RUSTBORO_CITY_DEVON_CORP_1F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_DEVON_CORP_2F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_DEVON_CORP_3F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_HOUSE1": "Rustboro_City_E.png",
            "RUSTBORO_CITY_HOUSE2": "Rustboro_City_E.png",
            "RUSTBORO_CITY_HOUSE3": "Rustboro_City_E.png",
            "RUSTBORO_CITY_MART": "Rustboro_City_E.png",
            "RUSTBORO_CITY_FLAT1_1F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_FLAT1_2F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_FLAT2_1F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_FLAT2_2F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_FLAT2_3F": "Rustboro_City_E.png",
            "RUSTBORO_CITY_GYM": "Rustboro_Gym_E.png",
        }

        # Map bank/number to location mapping (for coordinate-based lookup)
        self.coord_mapping: Dict[Tuple[int, int], str] = {
            # Add specific map bank/number mappings as needed
            # Format: (map_bank, map_number) -> location_id
        }

        logger.info(f"Initializing MapProvider with directory: {self.maps_directory}")
        self._load_available_maps()

    def _load_available_maps(self):
        """Scan directory and index all available map images"""
        if not self.maps_directory.exists():
            logger.warning(f"Maps directory does not exist: {self.maps_directory}")
            return

        # Scan for .png files
        png_files = list(self.maps_directory.glob("*.png"))
        logger.info(f"Found {len(png_files)} .png files in {self.maps_directory}")

        # Index each map
        for png_file in png_files:
            try:
                # Extract location name from filename
                # E.g., "Littleroot_Town_E.png" -> "Littleroot Town"
                location_name = png_file.stem  # Remove .png
                location_name = location_name.replace("_E", "")  # Remove _E suffix
                location_name = location_name.replace("_", " ")  # Underscores to spaces

                # Create map data (image loaded lazily)
                map_data = MapData(
                    location_name=location_name,
                    image_path=str(png_file),
                    description=f"Overview map of {location_name}"
                )

                # Index by filename (without extension)
                map_key = png_file.stem
                self.maps[map_key] = map_data

                logger.debug(f"Indexed map: {map_key} -> {location_name}")

            except Exception as e:
                logger.error(f"Error indexing map {png_file}: {e}", exc_info=True)

        # Build reverse mapping (location ID -> map key)
        for location_id, filename in self.location_mapping.items():
            map_key = Path(filename).stem
            if map_key in self.maps:
                self.location_to_map[location_id] = map_key
                logger.debug(f"Mapped location {location_id} -> {map_key}")

        logger.info(f"Successfully indexed {len(self.maps)} maps with {len(self.location_to_map)} location mappings")

    def _load_image(self, map_key: str) -> Optional[Image.Image]:
        """
        Load image from disk with caching.

        Args:
            map_key: Map key to load

        Returns:
            PIL Image or None if loading fails
        """
        # Check cache first
        if map_key in self._image_cache:
            logger.debug(f"Using cached image for {map_key}")
            return self._image_cache[map_key]

        # Get map data
        map_data = self.maps.get(map_key)
        if not map_data:
            logger.warning(f"No map data found for key: {map_key}")
            return None

        # Load image
        try:
            image_path = Path(map_data.image_path)
            if not image_path.exists():
                logger.error(f"Map image file not found: {image_path}")
                return None

            image = Image.open(image_path)
            logger.info(f"Loaded map image: {map_key} ({image.size[0]}x{image.size[1]})")

            # Cache the image
            self._image_cache[map_key] = image

            # Also update the map_data
            map_data.image = image

            return image

        except Exception as e:
            logger.error(f"Error loading map image {map_data.image_path}: {e}", exc_info=True)
            return None

    def get_map_for_location(self, location: str) -> Optional[MapData]:
        """
        Get map data for a game location.

        Args:
            location: Game location ID (e.g., "LITTLEROOT_TOWN", "ROUTE101")

        Returns:
            MapData with loaded image, or None if not found
        """
        # Normalize location
        location = location.upper().strip()

        # Look up map key
        map_key = self.location_to_map.get(location)
        if not map_key:
            logger.debug(f"No map mapping found for location: {location}")
            return None

        # Get map data
        map_data = self.maps.get(map_key)
        if not map_data:
            logger.warning(f"Map data not found for key: {map_key}")
            return None

        # Ensure image is loaded
        if map_data.image is None:
            image = self._load_image(map_key)
            if image is None:
                return None

        return map_data

    def get_map_for_milestone(self, milestone_id: str) -> Optional[MapData]:
        """
        Get map for a milestone by inferring location.

        Args:
            milestone_id: Milestone identifier (e.g., "STARTER_CHOSEN")

        Returns:
            MapData or None
        """
        # Milestone to location mapping
        milestone_locations = {
            "GAME_RUNNING": None,  # No map for title screen
            "INTRO_CUTSCENE_COMPLETE": "LITTLEROOT_TOWN",
            "PLAYER_HOUSE_ENTERED": "LITTLEROOT_TOWN",
            "PLAYER_BEDROOM": "LITTLEROOT_TOWN",
            "CLOCK_SET": "LITTLEROOT_TOWN",
            "RIVAL_HOUSE": "LITTLEROOT_TOWN",
            "RIVAL_BEDROOM": "LITTLEROOT_TOWN",
            "ROUTE_101": "ROUTE101",
            "STARTER_CHOSEN": "ROUTE101",
            "BIRCH_LAB_VISITED": "LITTLEROOT_TOWN",
            "OLDALE_TOWN": "OLDALE_TOWN",
            "ROUTE_103": "ROUTE103",
            "RECEIVED_POKEDEX": "LITTLEROOT_TOWN",
            "ROUTE_102": "ROUTE102",
            "PETALBURG_CITY": "PETALBURG_CITY",
            "DAD_FIRST_MEETING": "PETALBURG_CITY",
            "GYM_EXPLANATION": "PETALBURG_CITY",
            "ROUTE_104_SOUTH": "ROUTE104",
            "PETALBURG_WOODS": "PETALBURG_WOODS",
            "TEAM_AQUA_GRUNT_DEFEATED": "PETALBURG_WOODS",
            "ROUTE_104_NORTH": "ROUTE104",
            "RUSTBORO_CITY": "RUSTBORO_CITY",
            "RUSTBORO_GYM_ENTERED": "RUSTBORO_CITY_GYM",
            "ROXANNE_DEFEATED": "RUSTBORO_CITY_GYM",
            "FIRST_GYM_COMPLETE": "RUSTBORO_CITY_GYM",
        }

        location = milestone_locations.get(milestone_id)
        if not location:
            logger.debug(f"No location mapping for milestone: {milestone_id}")
            return None

        return self.get_map_for_location(location)

    def get_map_by_coords(self, map_bank: int, map_number: int) -> Optional[MapData]:
        """
        Get map by game map coordinates.

        Args:
            map_bank: Game map bank
            map_number: Game map number

        Returns:
            MapData or None
        """
        location = self.coord_mapping.get((map_bank, map_number))
        if not location:
            logger.debug(f"No location mapping for coords: ({map_bank}, {map_number})")
            return None

        return self.get_map_for_location(location)

    def get_available_maps(self) -> Dict[str, MapData]:
        """Get all available maps (without loading images)"""
        return self.maps.copy()

    def preload_all_maps(self):
        """Preload all map images into cache (useful for performance)"""
        logger.info(f"Preloading {len(self.maps)} map images...")
        for map_key in self.maps.keys():
            self._load_image(map_key)
        logger.info(f"Preloaded {len(self._image_cache)} map images")

    def clear_cache(self):
        """Clear the image cache to free memory"""
        self._image_cache.clear()
        for map_data in self.maps.values():
            map_data.image = None
        logger.info("Cleared map image cache")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "total_maps": len(self.maps),
            "cached_images": len(self._image_cache),
            "location_mappings": len(self.location_to_map)
        }

    def resize_map(self, map_data: MapData, max_size: int = 800) -> Optional[Image.Image]:
        """
        Resize map image to fit within max_size while preserving aspect ratio.

        Useful for reducing token count when sending to VLM.

        Args:
            map_data: MapData with loaded image
            max_size: Maximum width or height in pixels

        Returns:
            Resized PIL Image or None
        """
        if map_data.image is None:
            logger.warning("Cannot resize map: image not loaded")
            return None

        width, height = map_data.image.size

        # Check if resize needed
        if width <= max_size and height <= max_size:
            logger.debug(f"Map already within size limit: {width}x{height}")
            return map_data.image

        # Calculate new size preserving aspect ratio
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))

        # Resize
        resized = map_data.image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        logger.info(f"Resized map from {width}x{height} to {new_width}x{new_height}")

        return resized

    def __repr__(self):
        return f"MapProvider(maps={len(self.maps)}, cached={len(self._image_cache)})"
