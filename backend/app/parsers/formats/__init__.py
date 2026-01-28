"""Built-in evidence format parsers."""

from app.parsers.formats.evtx import WindowsEvtxParser
from app.parsers.formats.json import GenericJSONParser

# Export all parsers (imported conditionally to handle missing dependencies)
__all__ = [
    "WindowsEvtxParser",
    "GenericJSONParser",
]

# Dissect-based parsers
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

# Browser parsers - Chrome
try:
    from app.parsers.formats.browser_chrome import ChromeHistoryParser, ChromeLoginDataParser

    __all__.extend(["ChromeHistoryParser", "ChromeLoginDataParser"])
except ImportError:
    pass

# Browser parsers - Firefox
try:
    from app.parsers.formats.browser_firefox import FirefoxHistoryParser

    __all__.append("FirefoxHistoryParser")
except ImportError:
    pass

# Browser parsers - Edge
try:
    from app.parsers.formats.browser_edge import (
        EdgeBookmarksParser,
        EdgeDownloadsParser,
        EdgeHistoryParser,
    )

    __all__.extend(["EdgeHistoryParser", "EdgeDownloadsParser", "EdgeBookmarksParser"])
except ImportError:
    pass

# Linux log parsers
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

# Network parsers
try:
    from app.parsers.formats.pcap import PcapParser

    __all__.append("PcapParser")
except ImportError:
    pass

# Memory forensics
try:
    from app.parsers.formats.memory import MemoryParser

    __all__.append("MemoryParser")
except ImportError:
    pass

# Windows execution artifacts
try:
    from app.parsers.formats.shimcache import ShimcacheParser

    __all__.append("ShimcacheParser")
except ImportError:
    pass

try:
    from app.parsers.formats.amcache import AmcacheParser

    __all__.append("AmcacheParser")
except ImportError:
    pass

try:
    from app.parsers.formats.userassist import UserAssistParser

    __all__.append("UserAssistParser")
except ImportError:
    pass

# Windows system artifacts
try:
    from app.parsers.formats.srum import SRUMParser

    __all__.append("SRUMParser")
except ImportError:
    pass

try:
    from app.parsers.formats.recyclebin import RecycleBinParser

    __all__.append("RecycleBinParser")
except ImportError:
    pass

try:
    from app.parsers.formats.lnk import LnkParser

    __all__.append("LnkParser")
except ImportError:
    pass

try:
    from app.parsers.formats.jumplist import JumpListParser

    __all__.append("JumpListParser")
except ImportError:
    pass

# Remote access parsers
try:
    from app.parsers.formats.remoteaccess import AnyDeskParser, RustDeskParser, TeamViewerParser

    __all__.extend(["TeamViewerParser", "AnyDeskParser", "RustDeskParser"])
except ImportError:
    pass

# Web server parsers
try:
    from app.parsers.formats.webserver import (
        ApacheAccessParser,
        ApacheErrorParser,
        IISParser,
        NginxAccessParser,
    )

    __all__.extend(["ApacheAccessParser", "ApacheErrorParser", "NginxAccessParser", "IISParser"])
except ImportError:
    pass

# SSH parsers
try:
    from app.parsers.formats.ssh import AuthorizedKeysParser, KnownHostsParser, PuTTYParser

    __all__.extend(["AuthorizedKeysParser", "KnownHostsParser", "PuTTYParser"])
except ImportError:
    pass
