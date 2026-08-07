from .benchmark import (
    RetrievalBenchmarkCase,
    RetrievalBenchmarkReport,
    RetrievalBenchmarkRunner,
)
from .fence import MemoryRevisionFence
from .index import IndexHit, SQLiteDerivedIndex
from .migration import MigrationReport, SQLiteMigrationController, StoreManifest
from .recovery import (
    FailClosedRetrievalGateway,
    OutboxHealthReport,
    OutboxRecoveryReport,
    SQLiteOutboxRecovery,
)
from .resilience import (
    IndexHealthReport,
    IndexHealthStatus,
    IndexRebuildReport,
    ReplayVerification,
    RetrievalReplayEvidence,
    RetrievalReplayVerifier,
    SQLiteIndexResilience,
)
from .retrieval import (
    BudgetConsumption,
    ChannelContribution,
    ProgressiveMemoryRetriever,
    RecallChannel,
    ReleasedMemory,
    RetrievalRequest,
    RetrievalResult,
    RetrievalStage,
    RetrievalStatus,
    StageBudget,
)
from .sqlite_fenced import FencedSQLiteMemoryStore, MemoryFenceViolation

# Public SQLite profile now includes the I3 derived-Memory parent fence. The
# subclass is behavior-identical to the M1B Store for ordinary writes and only
# activates the extra fence for consolidation-derived revisions.
SQLiteMemoryStore = FencedSQLiteMemoryStore

__all__ = [
    "BudgetConsumption",
    "ChannelContribution",
    "FailClosedRetrievalGateway",
    "FencedSQLiteMemoryStore",
    "IndexHealthReport",
    "IndexHealthStatus",
    "IndexHit",
    "IndexRebuildReport",
    "MemoryFenceViolation",
    "MemoryRevisionFence",
    "MigrationReport",
    "OutboxHealthReport",
    "OutboxRecoveryReport",
    "ProgressiveMemoryRetriever",
    "RecallChannel",
    "ReleasedMemory",
    "ReplayVerification",
    "RetrievalBenchmarkCase",
    "RetrievalBenchmarkReport",
    "RetrievalBenchmarkRunner",
    "RetrievalReplayEvidence",
    "RetrievalReplayVerifier",
    "RetrievalRequest",
    "RetrievalResult",
    "RetrievalStage",
    "RetrievalStatus",
    "SQLiteDerivedIndex",
    "SQLiteIndexResilience",
    "SQLiteMemoryStore",
    "SQLiteMigrationController",
    "SQLiteOutboxRecovery",
    "StageBudget",
    "StoreManifest",
]
