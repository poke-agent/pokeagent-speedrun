"""
Performance Metrics System for Agent

Phase 3.2 implementation from TRACK2_SIMPLE_AGENT_OPTIMIZATION_PLAN.md

Tracks detailed performance metrics for optimization analysis and submission documentation.
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """Single point-in-time metric measurement"""
    timestamp: str
    step_number: int
    total_actions: int
    vlm_calls: int
    frame_skips: int
    battles_won: int
    battles_lost: int
    current_location: str
    milestones_completed: int


class PerformanceMetrics:
    """
    Comprehensive performance tracking system.

    Tracks:
    - Action counts
    - VLM call statistics
    - Battle performance
    - Milestone progress
    - Optimization effectiveness
    """

    def __init__(self, metrics_dir: str = ".pokeagent_cache/metrics"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        # Session start time
        self.session_start = time.time()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Counters
        self.total_actions = 0
        self.total_vlm_calls = 0
        self.frame_skips = 0
        self.battles_initiated = 0
        self.battles_won = 0
        self.battles_lost = 0
        self.dialogue_handled = 0
        self.navigation_successful = 0
        self.navigation_failed = 0

        # Timing metrics
        self.vlm_call_times: List[float] = []
        self.action_times: List[float] = []

        # Milestone tracking
        self.milestones_completed: List[str] = []
        self.milestone_action_counts: Dict[str, int] = {}

        # Context distribution
        self.context_counts = defaultdict(int)

        # Snapshots for timeline analysis
        self.snapshots: List[MetricSnapshot] = []
        self.last_snapshot_step = 0
        self.snapshot_interval = 100  # Take snapshot every 100 actions

        # Optimization effectiveness
        self.optimization_stats = {
            'frame_skips_saved_calls': 0,
            'battle_analyzer_used': 0,
            'strategic_memory_hits': 0,
            'speedrun_router_guidance': 0
        }

        logger.info(f"Performance Metrics initialized for session {self.session_id}")

    def log_action(self, action: str, context: str, duration: float = 0.0):
        """Log a single action"""
        self.total_actions += 1
        self.context_counts[context] += 1

        if duration > 0:
            self.action_times.append(duration)

    def log_vlm_call(self, duration: float, tokens_used: Optional[int] = None):
        """Log a VLM API call"""
        self.total_vlm_calls += 1
        self.vlm_call_times.append(duration)

    def log_frame_skip(self):
        """Log a skipped frame"""
        self.frame_skips += 1
        self.optimization_stats['frame_skips_saved_calls'] += 1

    def log_battle_start(self):
        """Log battle initiation"""
        self.battles_initiated += 1

    def log_battle_end(self, outcome: str):
        """Log battle outcome"""
        if outcome == "win":
            self.battles_won += 1
        elif outcome == "loss":
            self.battles_lost += 1

    def log_navigation(self, success: bool):
        """Log navigation attempt"""
        if success:
            self.navigation_successful += 1
        else:
            self.navigation_failed += 1

    def log_milestone(self, milestone_id: str):
        """Log milestone completion"""
        if milestone_id not in self.milestones_completed:
            self.milestones_completed.append(milestone_id)
            self.milestone_action_counts[milestone_id] = self.total_actions
            logger.info(f"📊 Milestone reached: {milestone_id} at action {self.total_actions}")

    def log_optimization_use(self, optimization: str):
        """Log usage of an optimization feature"""
        if optimization in self.optimization_stats:
            self.optimization_stats[optimization] += 1

    def take_snapshot(self, current_location: str):
        """Take a performance snapshot"""
        snapshot = MetricSnapshot(
            timestamp=datetime.now().isoformat(),
            step_number=self.total_actions,
            total_actions=self.total_actions,
            vlm_calls=self.total_vlm_calls,
            frame_skips=self.frame_skips,
            battles_won=self.battles_won,
            battles_lost=self.battles_lost,
            current_location=current_location,
            milestones_completed=len(self.milestones_completed)
        )
        self.snapshots.append(snapshot)

    def maybe_take_snapshot(self, current_location: str):
        """Take snapshot if interval has passed"""
        if self.total_actions - self.last_snapshot_step >= self.snapshot_interval:
            self.take_snapshot(current_location)
            self.last_snapshot_step = self.total_actions

    def get_current_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        elapsed = time.time() - self.session_start

        # Calculate averages
        avg_vlm_time = sum(self.vlm_call_times) / len(self.vlm_call_times) if self.vlm_call_times else 0
        avg_action_time = sum(self.action_times) / len(self.action_times) if self.action_times else 0

        # Calculate rates
        actions_per_minute = (self.total_actions / elapsed * 60) if elapsed > 0 else 0
        vlm_calls_per_minute = (self.total_vlm_calls / elapsed * 60) if elapsed > 0 else 0

        # Battle statistics
        battle_win_rate = (self.battles_won / self.battles_initiated * 100) if self.battles_initiated > 0 else 0
        navigation_success_rate = (
            self.navigation_successful / (self.navigation_successful + self.navigation_failed) * 100
            if (self.navigation_successful + self.navigation_failed) > 0 else 0
        )

        # Optimization effectiveness
        frame_skip_rate = (self.frame_skips / self.total_actions * 100) if self.total_actions > 0 else 0
        vlm_efficiency = (self.total_actions / self.total_vlm_calls) if self.total_vlm_calls > 0 else 0

        return {
            'session': {
                'session_id': self.session_id,
                'elapsed_seconds': elapsed,
                'elapsed_minutes': elapsed / 60
            },
            'actions': {
                'total': self.total_actions,
                'per_minute': actions_per_minute,
                'avg_duration': avg_action_time
            },
            'vlm': {
                'total_calls': self.total_vlm_calls,
                'per_minute': vlm_calls_per_minute,
                'avg_duration': avg_vlm_time,
                'actions_per_call': vlm_efficiency
            },
            'battles': {
                'initiated': self.battles_initiated,
                'won': self.battles_won,
                'lost': self.battles_lost,
                'win_rate': battle_win_rate
            },
            'navigation': {
                'successful': self.navigation_successful,
                'failed': self.navigation_failed,
                'success_rate': navigation_success_rate
            },
            'optimization': {
                'frame_skips': self.frame_skips,
                'frame_skip_rate': frame_skip_rate,
                **self.optimization_stats
            },
            'milestones': {
                'completed': len(self.milestones_completed),
                'list': self.milestones_completed
            },
            'context_distribution': dict(self.context_counts)
        }

    def generate_report(self) -> str:
        """Generate human-readable performance report"""
        stats = self.get_current_stats()

        lines = [
            "=" * 60,
            "PERFORMANCE METRICS REPORT",
            "=" * 60,
            f"Session: {stats['session']['session_id']}",
            f"Duration: {stats['session']['elapsed_minutes']:.1f} minutes",
            "",
            "ACTIONS:",
            f"  Total: {stats['actions']['total']}",
            f"  Rate: {stats['actions']['per_minute']:.1f} actions/minute",
            "",
            "VLM CALLS:",
            f"  Total: {stats['vlm']['total_calls']}",
            f"  Rate: {stats['vlm']['per_minute']:.1f} calls/minute",
            f"  Avg Duration: {stats['vlm']['avg_duration']:.2f}s",
            f"  Actions per Call: {stats['vlm']['actions_per_call']:.2f}",
            "",
            "BATTLES:",
            f"  Initiated: {stats['battles']['initiated']}",
            f"  Won: {stats['battles']['won']}",
            f"  Lost: {stats['battles']['lost']}",
            f"  Win Rate: {stats['battles']['win_rate']:.1f}%",
            "",
            "OPTIMIZATION EFFECTIVENESS:",
            f"  Frame Skips: {stats['optimization']['frame_skips']} ({stats['optimization']['frame_skip_rate']:.1f}% of actions)",
            f"  Saved VLM Calls: {stats['optimization']['frame_skips_saved_calls']}",
            f"  Battle Analyzer Uses: {stats['optimization']['battle_analyzer_used']}",
            f"  Strategic Memory Hits: {stats['optimization']['strategic_memory_hits']}",
            "",
            "MILESTONES:",
            f"  Completed: {stats['milestones']['completed']}",
        ]

        if stats['milestones']['list']:
            lines.append("  Recent:")
            for milestone in stats['milestones']['list'][-5:]:
                actions = self.milestone_action_counts.get(milestone, '?')
                lines.append(f"    • {milestone} (action {actions})")

        lines.append("=" * 60)

        return "\n".join(lines)

    def save_session_data(self):
        """Save session data to file"""
        try:
            session_file = self.metrics_dir / f"session_{self.session_id}.json"

            data = {
                'session_info': {
                    'session_id': self.session_id,
                    'start_time': datetime.fromtimestamp(self.session_start).isoformat(),
                    'duration_seconds': time.time() - self.session_start
                },
                'statistics': self.get_current_stats(),
                'snapshots': [asdict(snapshot) for snapshot in self.snapshots],
                'milestone_action_counts': self.milestone_action_counts
            }

            with open(session_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved session data to {session_file}")

        except Exception as e:
            logger.error(f"Failed to save session data: {e}")

    def export_for_submission(self) -> Dict[str, Any]:
        """Export metrics in format suitable for competition submission"""
        stats = self.get_current_stats()

        return {
            'session_id': self.session_id,
            'total_actions': self.total_actions,
            'duration_minutes': stats['session']['elapsed_minutes'],
            'milestones_completed': len(self.milestones_completed),
            'milestone_list': self.milestones_completed,
            'actions_per_milestone': self.milestone_action_counts,
            'efficiency_metrics': {
                'actions_per_minute': stats['actions']['per_minute'],
                'vlm_calls_total': self.total_vlm_calls,
                'actions_per_vlm_call': stats['vlm']['actions_per_call'],
                'battle_win_rate': stats['battles']['win_rate'],
                'frame_skip_savings': stats['optimization']['frame_skips']
            },
            'optimization_usage': self.optimization_stats
        }


# Global metrics instance for easy access
_global_metrics: Optional[PerformanceMetrics] = None


def get_metrics() -> PerformanceMetrics:
    """Get or create global metrics instance"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = PerformanceMetrics()
    return _global_metrics


def log_action(action: str, context: str, duration: float = 0.0):
    """Convenience function to log action"""
    get_metrics().log_action(action, context, duration)


def log_vlm_call(duration: float, tokens_used: Optional[int] = None):
    """Convenience function to log VLM call"""
    get_metrics().log_vlm_call(duration, tokens_used)


def save_final_report():
    """Save final report at session end"""
    metrics = get_metrics()
    metrics.save_session_data()
    print("\n" + metrics.generate_report())
