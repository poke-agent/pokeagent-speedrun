"""
History Compression for Simple Agent

Phase 3.1 implementation from TRACK2_SIMPLE_AGENT_OPTIMIZATION_PLAN.md

Compresses old history entries to save context space while retaining important information.
Uses intelligent summarization to batch similar consecutive actions.
"""

import logging
from typing import List, Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class HistoryCompressor:
    """
    Compresses agent history to reduce prompt token usage.

    Keeps recent entries in full detail, summarizes older entries.
    """

    def __init__(self, full_detail_count: int = 20, summary_batch_size: int = 10):
        """
        Initialize history compressor.

        Args:
            full_detail_count: Number of recent entries to keep in full detail
            summary_batch_size: How many old entries to batch into one summary
        """
        self.full_detail_count = full_detail_count
        self.summary_batch_size = summary_batch_size

    def compress_history(self, history_entries: List[Any]) -> str:
        """
        Compress history entries into a compact string representation.

        Args:
            history_entries: List of HistoryEntry objects

        Returns:
            Compressed string representation
        """
        if not history_entries:
            return "No history."

        total_entries = len(history_entries)

        # Keep recent entries in full detail
        recent_entries = history_entries[-self.full_detail_count:]
        old_entries = history_entries[:-self.full_detail_count] if total_entries > self.full_detail_count else []

        lines = []

        # Summarize old entries if they exist
        if old_entries:
            summary = self._summarize_old_entries(old_entries)
            lines.append(f"[Earlier: {summary}]")
            lines.append("")  # Blank line separator

        # Show recent entries in full detail
        lines.append("RECENT HISTORY:")
        for i, entry in enumerate(recent_entries, 1):
            coord_str = f"({entry.player_coords[0]},{entry.player_coords[1]})" if entry.player_coords else "(?)"

            # Simplified action display (remove reasoning for brevity)
            action = entry.action_taken.split("|")[0].strip() if "|" in entry.action_taken else entry.action_taken

            lines.append(f"{i}. {entry.context} @ {coord_str}: {action}")

        return "\n".join(lines)

    def _summarize_old_entries(self, old_entries: List[Any]) -> str:
        """
        Create a compact summary of old history entries.

        Groups consecutive similar actions and locations.
        """
        if not old_entries:
            return ""

        # Batch entries and create summaries
        batches = self._create_batches(old_entries, self.summary_batch_size)

        summaries = []
        for batch_start, batch_end, batch_entries in batches:
            summary = self._summarize_batch(batch_entries)
            summaries.append(f"Actions {batch_start}-{batch_end}: {summary}")

        return " | ".join(summaries)

    def _create_batches(self, entries: List[Any], batch_size: int) -> List[tuple]:
        """Create batches of entries for summarization"""
        batches = []
        total = len(entries)

        for i in range(0, total, batch_size):
            batch = entries[i:i + batch_size]
            batch_start = i + 1
            batch_end = min(i + batch_size, total)
            batches.append((batch_start, batch_end, batch))

        return batches

    def _summarize_batch(self, batch: List[Any]) -> str:
        """
        Summarize a batch of history entries.

        Identifies patterns:
        - Movement sequences (e.g., "moved UP 3 times")
        - Location changes (e.g., "traveled from X to Y")
        - Context changes (e.g., "entered battle, won")
        """
        if not batch:
            return "empty"

        # Count action types
        action_counts = defaultdict(int)
        contexts = []
        locations = []
        start_coords = None
        end_coords = None

        for entry in batch:
            # Extract action (remove reasoning)
            action = entry.action_taken.split("|")[0].strip() if "|" in entry.action_taken else entry.action_taken
            action_word = action.split()[0].split(",")[0]  # Get first action word
            action_counts[action_word] += 1

            # Track contexts
            if entry.context not in contexts:
                contexts.append(entry.context)

            # Track coordinate changes
            if entry.player_coords:
                if start_coords is None:
                    start_coords = entry.player_coords
                end_coords = entry.player_coords

        # Build summary
        parts = []

        # Context summary
        if len(contexts) == 1:
            parts.append(contexts[0])
        else:
            parts.append(f"{'/'.join(contexts)}")

        # Movement summary
        movements = {k: v for k, v in action_counts.items() if k in ["UP", "DOWN", "LEFT", "RIGHT"]}
        if movements:
            move_summary = ", ".join([f"{k}×{v}" for k, v in sorted(movements.items(), key=lambda x: x[1], reverse=True)])
            parts.append(f"moved ({move_summary})")

        # Other actions
        other_actions = {k: v for k, v in action_counts.items() if k not in ["UP", "DOWN", "LEFT", "RIGHT"]}
        if other_actions:
            for action, count in sorted(other_actions.items(), key=lambda x: x[1], reverse=True)[:3]:  # Top 3
                if count > 1:
                    parts.append(f"{action}×{count}")
                else:
                    parts.append(action)

        # Coordinate change
        if start_coords and end_coords and start_coords != end_coords:
            parts.append(f"{start_coords}→{end_coords}")

        return ", ".join(parts) if parts else "various actions"

    def compress_action_list(self, actions: List[str], max_display: int = 20) -> str:
        """
        Compress a list of recent actions into a compact string.

        Args:
            actions: List of action strings
            max_display: Maximum number to show in detail

        Returns:
            Compressed action string
        """
        if not actions:
            return "None"

        total = len(actions)

        if total <= max_display:
            # Show all actions
            return ", ".join(actions)

        # Show recent actions + summary of older
        recent = actions[-max_display:]
        old_count = total - max_display

        # Summarize old actions
        old_actions = actions[:-max_display]
        old_summary = self._summarize_action_list(old_actions)

        return f"[Earlier {old_count}: {old_summary}] | Recent: {', '.join(recent)}"

    def _summarize_action_list(self, actions: List[str]) -> str:
        """Summarize a list of actions"""
        if not actions:
            return "none"

        # Count each action type
        action_counts = defaultdict(int)
        for action in actions:
            action_counts[action] += 1

        # Create summary (top 5 most common)
        top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        summary_parts = [f"{action}×{count}" for action, count in top_actions]

        return ", ".join(summary_parts)

    def compress_objectives(self, objectives: List[Any]) -> str:
        """
        Compress objectives list for prompt.

        Shows active objectives in full, completed objectives as count.
        """
        active = [obj for obj in objectives if not obj.completed]
        completed = [obj for obj in objectives if obj.completed]

        lines = []

        # Completed summary
        if completed:
            storyline_completed = sum(1 for obj in completed if obj.storyline)
            other_completed = len(completed) - storyline_completed
            lines.append(f"✅ Completed: {storyline_completed} story, {other_completed} sub-objectives")

        # Active objectives (full detail)
        if active:
            lines.append("\n📋 ACTIVE OBJECTIVES:")
            for i, obj in enumerate(active[:10], 1):  # Max 10 to keep prompt manageable
                status_icon = "📍" if obj.storyline else "🎯"
                lines.append(f"{i}. {status_icon} {obj.description}")
                if obj.target_coords:
                    lines.append(f"   → Target: {obj.target_coords}")
                if obj.notes and not obj.storyline:
                    lines.append(f"   💡 {obj.notes}")
        else:
            lines.append("\n✨ All objectives complete!")

        return "\n".join(lines)

    def estimate_token_savings(self, original_length: int, compressed_length: int) -> Dict[str, Any]:
        """
        Estimate token savings from compression.

        Rough estimation: 1 token ≈ 4 characters for English text
        """
        original_tokens = original_length // 4
        compressed_tokens = compressed_length // 4
        saved_tokens = original_tokens - compressed_tokens
        savings_pct = (saved_tokens / original_tokens * 100) if original_tokens > 0 else 0

        return {
            'original_chars': original_length,
            'compressed_chars': compressed_length,
            'original_tokens_est': original_tokens,
            'compressed_tokens_est': compressed_tokens,
            'saved_tokens': saved_tokens,
            'savings_percent': savings_pct
        }


# Convenience function for use in agent
def compress_history_for_prompt(
    history_entries: List[Any],
    full_detail_count: int = 20,
    summary_batch_size: int = 10
) -> str:
    """
    Compress history entries for prompt inclusion.

    Args:
        history_entries: List of HistoryEntry objects
        full_detail_count: Number of recent entries in full detail
        summary_batch_size: Size of batches for summarization

    Returns:
        Compressed history string
    """
    compressor = HistoryCompressor(
        full_detail_count=full_detail_count,
        summary_batch_size=summary_batch_size
    )
    return compressor.compress_history(history_entries)


def compress_actions_for_prompt(
    actions: List[str],
    max_display: int = 20
) -> str:
    """
    Compress action list for prompt inclusion.

    Args:
        actions: List of action strings
        max_display: Maximum actions to show in detail

    Returns:
        Compressed action string
    """
    compressor = HistoryCompressor()
    return compressor.compress_action_list(actions, max_display)
