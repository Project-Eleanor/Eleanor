"""Detection engines for Eleanor.

Provides pattern matching and threat detection using:
- YARA rules for malware/IOC detection
- Sigma rules for log-based detection
"""

from app.detection.sigma_engine import SigmaEngine
from app.detection.yara_scanner import YaraScanner

__all__ = ["YaraScanner", "SigmaEngine"]
