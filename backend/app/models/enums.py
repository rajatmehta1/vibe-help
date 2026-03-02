import enum


class OrgRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class PolicyCategory(str, enum.Enum):
    SECURITY = "security"
    NAMING = "naming"
    ARCHITECTURE = "architecture"
    ERROR_HANDLING = "error_handling"
    DEPENDENCIES = "dependencies"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    CUSTOM = "custom"


class SeverityLevel(str, enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ScanType(str, enum.Enum):
    REALTIME = "realtime"
    FILE = "file"
    WORKSPACE = "workspace"


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditAction(str, enum.Enum):
    CODE_DETECTED = "code_detected"
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    INDEX_STARTED = "index_started"
    INDEX_COMPLETED = "index_completed"


class IndexingJobType(str, enum.Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


class CodeUnitType(str, enum.Enum):
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    FILE = "file"
