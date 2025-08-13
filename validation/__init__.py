"""
Validation Framework Module

A modular validation system for data package validation
with support for multiple validation types and extensibility.
"""

from .base import ValidationResult, ValidationLevel, BaseValidator
from .manager import ValidationManager
from .metacam import MetaCamValidator

# 尝试导入TransientValidator，如果依赖不可用则跳过
try:
    from .transient_validator import TransientValidator
    TRANSIENT_VALIDATOR_AVAILABLE = True
except ImportError as e:
    print(f"Warning: TransientValidator not available: {e}")
    TransientValidator = None
    TRANSIENT_VALIDATOR_AVAILABLE = False

__all__ = [
    'ValidationResult', 
    'ValidationLevel', 
    'BaseValidator',
    'ValidationManager',
    'MetaCamValidator'
]

if TRANSIENT_VALIDATOR_AVAILABLE:
    __all__.append('TransientValidator')