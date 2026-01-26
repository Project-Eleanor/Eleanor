"""Mock adapters for testing Eleanor integrations."""

from tests.mocks.velociraptor import MockVelociraptorAdapter
from tests.mocks.iris import MockIRISAdapter
from tests.mocks.opencti import MockOpenCTIAdapter
from tests.mocks.shuffle import MockShuffleAdapter
from tests.mocks.timesketch import MockTimesketchAdapter

__all__ = [
    "MockVelociraptorAdapter",
    "MockIRISAdapter",
    "MockOpenCTIAdapter",
    "MockShuffleAdapter",
    "MockTimesketchAdapter",
]
