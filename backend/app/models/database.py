import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    AuditAction,
    CodeUnitType,
    IndexingJobType,
    OrgRole,
    PolicyCategory,
    ScanStatus,
    ScanType,
    SeverityLevel,
)

# ---------------------------------------------------------------------------
# Association table
# ---------------------------------------------------------------------------

user_organizations = Table(
    "user_organizations",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("org_id", UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
    Column("role", Enum(OrgRole, name="org_role", create_constraint=True, values_callable=lambda e: [x.value for x in e]), nullable=False, default=OrgRole.MEMBER),
)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(1024), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organizations = relationship("Organization", secondary=user_organizations, back_populates="members", lazy="selectin")
    audit_logs = relationship("AuditLog", back_populates="user", lazy="selectin")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members = relationship("User", secondary=user_organizations, back_populates="organizations", lazy="selectin")
    projects = relationship("Project", back_populates="organization", lazy="selectin")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    primary_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="projects", lazy="selectin")
    policies = relationship("Policy", back_populates="project", lazy="selectin")
    scans = relationship("Scan", back_populates="project", lazy="selectin")
    indexing_jobs = relationship("IndexingJob", back_populates="project", lazy="selectin")
    audit_logs = relationship("AuditLog", back_populates="project", lazy="selectin")
    code_embeddings = relationship("CodeEmbedding", back_populates="project", lazy="selectin")


class PolicyTemplate(Base):
    __tablename__ = "policy_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[PolicyCategory] = mapped_column(Enum(PolicyCategory, name="policy_category", create_constraint=True, values_callable=lambda e: [x.value for x in e]), nullable=False)
    default_severity: Mapped[SeverityLevel] = mapped_column(Enum(SeverityLevel, name="severity_level", create_constraint=True, values_callable=lambda e: [x.value for x in e]), nullable=False)
    default_configuration: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    policies = relationship("Policy", back_populates="template", lazy="selectin")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    policy_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policy_templates.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[PolicyCategory] = mapped_column(Enum(PolicyCategory, name="policy_category", create_constraint=True, create_type=False, values_callable=lambda e: [x.value for x in e]), nullable=False)
    severity_default: Mapped[SeverityLevel] = mapped_column(Enum(SeverityLevel, name="severity_level", create_constraint=True, create_type=False, values_callable=lambda e: [x.value for x in e]), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    configuration: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    project = relationship("Project", back_populates="policies", lazy="selectin")
    template = relationship("PolicyTemplate", back_populates="policies", lazy="selectin")
    violations = relationship("Violation", back_populates="policy", lazy="selectin")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scan_type: Mapped[ScanType] = mapped_column(Enum(ScanType, name="scan_type", create_constraint=True, values_callable=lambda e: [x.value for x in e]), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus, name="scan_status", create_constraint=True, values_callable=lambda e: [x.value for x in e]), nullable=False, default=ScanStatus.PENDING)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    trigger_source: Mapped[str] = mapped_column(String(50), nullable=False)
    total_violations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    project = relationship("Project", back_populates="scans", lazy="selectin")
    violations = relationship("Violation", back_populates="scan", lazy="selectin")


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    severity: Mapped[SeverityLevel] = mapped_column(Enum(SeverityLevel, name="severity_level", create_constraint=True, create_type=False, values_callable=lambda e: [x.value for x in e]), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    column_start: Mapped[int] = mapped_column(Integer, nullable=False)
    column_end: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    auto_fix: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    scan = relationship("Scan", back_populates="violations", lazy="selectin")
    policy = relationship("Policy", back_populates="violations", lazy="selectin")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction, name="audit_action", create_constraint=True, values_callable=lambda e: [x.value for x in e]), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="audit_logs", lazy="selectin")
    user = relationship("User", back_populates="audit_logs", lazy="selectin")


class IndexingJob(Base):
    __tablename__ = "indexing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus, name="scan_status", create_constraint=True, create_type=False, values_callable=lambda e: [x.value for x in e]), nullable=False, default=ScanStatus.PENDING)
    job_type: Mapped[IndexingJobType] = mapped_column(Enum(IndexingJobType, name="indexing_job_type", create_constraint=True, values_callable=lambda e: [x.value for x in e]), nullable=False)
    total_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_files: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="indexing_jobs", lazy="selectin")


class CodeEmbedding(Base):
    __tablename__ = "code_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    code_unit_type: Mapped[CodeUnitType] = mapped_column(Enum(CodeUnitType, name="code_unit_type", create_constraint=True, values_callable=lambda e: [x.value for x in e]), nullable=False)
    code_unit_name: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding = mapped_column(Vector(384), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    project = relationship("Project", back_populates="code_embeddings", lazy="selectin")
