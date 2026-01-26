"""Built-in evidence format parsers."""

from app.parsers.formats.evtx import WindowsEvtxParser
from app.parsers.formats.json import GenericJSONParser

# Export all parsers (imported conditionally to handle missing dependencies)
__all__ = [
    "WindowsEvtxParser",
    "GenericJSONParser",
]

# Try to import Dissect-based parsers
try:
    from app.parsers.formats.registry_hive import WindowsRegistryParser
    __all__.append("WindowsRegistryParser")
except ImportError:
    pass

try:
    from app.parsers.formats.prefetch import WindowsPrefetchParser
    __all__.append("WindowsPrefetchParser")
except ImportError:
    pass

try:
    from app.parsers.formats.mft import NTFSMftParser
    __all__.append("NTFSMftParser")
except ImportError:
    pass

try:
    from app.parsers.formats.usn_journal import UsnJournalParser
    __all__.append("UsnJournalParser")
except ImportError:
    pass

try:
    from app.parsers.formats.scheduled_tasks import WindowsScheduledTasksParser
    __all__.append("WindowsScheduledTasksParser")
except ImportError:
    pass

try:
    from app.parsers.formats.browser_chrome import ChromeHistoryParser, ChromeLoginDataParser
    __all__.extend(["ChromeHistoryParser", "ChromeLoginDataParser"])
except ImportError:
    pass

try:
    from app.parsers.formats.browser_firefox import FirefoxHistoryParser
    __all__.append("FirefoxHistoryParser")
except ImportError:
    pass

try:
    from app.parsers.formats.linux_auth import LinuxAuthLogParser
    __all__.append("LinuxAuthLogParser")
except ImportError:
    pass

try:
    from app.parsers.formats.linux_syslog import LinuxSyslogParser
    __all__.append("LinuxSyslogParser")
except ImportError:
    pass

try:
    from app.parsers.formats.pcap import PcapParser
    __all__.append("PcapParser")
except ImportError:
    pass
