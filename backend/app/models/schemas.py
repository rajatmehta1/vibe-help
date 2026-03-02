import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

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
# User
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------


class OrganizationCreate(BaseModel):
    name: str
    slug: str


class OrganizationUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class UserOrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: OrgRole


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    org_id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    root_path: str | None = None
    primary_language: str | None = None
    settings: dict | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    root_path: str | None = None
    primary_language: str | None = None
    settings: dict | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    root_path: str | None
    primary_language: str | None
    settings: dict | None
    created_at: datetime
    updated_at: datetime
    last_indexed_at: datetime | None


# ---------------------------------------------------------------------------
# PolicyTemplate
# ---------------------------------------------------------------------------


class PolicyTemplateCreate(BaseModel):
    slug: str
    name: str
    description: str | None = None
    category: PolicyCategory
    default_severity: SeverityLevel
    default_configuration: dict | None = None
    is_builtin: bool = False
    version: str | None = None


class PolicyTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: PolicyCategory | None = None
    default_severity: SeverityLevel | None = None
    default_configuration: dict | None = None
    version: str | None = None


class PolicyTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    category: PolicyCategory
    default_severity: SeverityLevel
    default_configuration: dict | None
    is_builtin: bool
    version: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    project_id: uuid.UUID
    policy_template_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    category: PolicyCategory
    severity_default: SeverityLevel
    is_active: bool = True
    configuration: dict | None = None


class PolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: PolicyCategory | None = None
    severity_default: SeverityLevel | None = None
    is_active: bool | None = None
    configuration: dict | None = None


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    policy_template_id: uuid.UUID | None
    name: str
    description: str | None
    category: PolicyCategory
    severity_default: SeverityLevel
    is_active: bool
    configuration: dict | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


class ScanCreate(BaseModel):
    project_id: uuid.UUID
    scan_type: ScanType
    file_path: str | None = None
    trigger_source: str


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    scan_type: ScanType
    status: ScanStatus
    file_path: str | None
    trigger_source: str
    total_violations: int
    started_at: datetime | None
    completed_at: datetime | None
    metadata_: dict | None = None


# ---------------------------------------------------------------------------
# Violation
# ---------------------------------------------------------------------------


class ViolationCreate(BaseModel):
    scan_id: uuid.UUID
    policy_id: uuid.UUID
    severity: SeverityLevel
    file_path: str
    line_start: int
    line_end: int
    column_start: int
    column_end: int
    message: str
    suggestion: str | None = None
    context_evidence: dict | None = None
    auto_fix: dict | None = None
    code_snippet: str | None = None


class ViolationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_id: uuid.UUID
    policy_id: uuid.UUID
    severity: SeverityLevel
    file_path: str
    line_start: int
    line_end: int
    column_start: int
    column_end: int
    message: str
    suggestion: str | None
    context_evidence: dict | None
    auto_fix: dict | None
    code_snippet: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class AuditLogCreate(BaseModel):
    project_id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: AuditAction
    details: dict | None = None
    ip_address: str | None = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID | None
    action: AuditAction
    details: dict | None
    ip_address: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# IndexingJob
# ---------------------------------------------------------------------------


class IndexingJobCreate(BaseModel):
    project_id: uuid.UUID
    job_type: IndexingJobType


class IndexingJobUpdate(BaseModel):
    status: ScanStatus | None = None
    total_files: int | None = None
    processed_files: int | None = None
    error_message: str | None = None


class IndexingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: ScanStatus
    job_type: IndexingJobType
    total_files: int
    processed_files: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


# ---------------------------------------------------------------------------
# CodeEmbedding
# ---------------------------------------------------------------------------


class CodeEmbeddingCreate(BaseModel):
    project_id: uuid.UUID
    file_path: str
    code_unit_type: CodeUnitType
    code_unit_name: str
    content_hash: str
    embedding: list[float] | None = None
    metadata_: dict | None = None


class CodeEmbeddingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    file_path: str
    code_unit_type: CodeUnitType
    code_unit_name: str
    content_hash: str
    metadata_: dict | None = None
    created_at: datetime
    updated_at: datetime
