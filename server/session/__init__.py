"""
Robust Session Management Module

This module provides connection-resilient session management with:
- Operation tracking with state machine
- Write-ahead logging for atomic operations
- Automatic checkpointing
- Session recovery after connection drops
- Standard Operating Procedures (SOP) for consistent work patterns
"""

from .operations import OperationTracker, Operation, OperationState
from .wal import WriteAheadLog, WALEntry
from .checkpoint import CheckpointManager
from .manager import RobustSessionManager, get_robust_session_manager
from .sop import SOPManager, get_sop_manager, WorkPattern, StandardOperatingProcedure

__all__ = [
    'OperationTracker',
    'Operation',
    'OperationState',
    'WriteAheadLog',
    'WALEntry',
    'CheckpointManager',
    'RobustSessionManager',
    'get_robust_session_manager',
    'SOPManager',
    'get_sop_manager',
    'WorkPattern',
    'StandardOperatingProcedure',
]
