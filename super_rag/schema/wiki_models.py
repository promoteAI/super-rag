from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WikiPageBase(BaseModel):
    slug: str = Field(..., description="URL-friendly slug, e.g. entity/acme-corp")
    title: str = Field(..., description="Human-readable title")
    page_type: str = Field("summary", description="summary|entity|concept|index|log|synthesis|comparison")
    content: str = Field("", description="Full markdown content")
    summary: str = Field("", description="One-line summary")
    aliases: Optional[List[str]] = Field(default_factory=list)
    source_refs: Optional[List[str]] = Field(default_factory=list)
    chunk_refs: Optional[List[str]] = Field(default_factory=list)
    in_links: Optional[List[str]] = Field(default_factory=list)
    out_links: Optional[List[str]] = Field(default_factory=list)
    page_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    status: Optional[str] = Field("published")


class WikiPageCreate(WikiPageBase):
    pass


class WikiPageUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    page_type: Optional[str] = None
    status: Optional[str] = None
    aliases: Optional[List[str]] = None
    source_refs: Optional[List[str]] = None
    chunk_refs: Optional[List[str]] = None
    page_metadata: Optional[Dict[str, Any]] = None


class WikiPage(WikiPageBase):
    id: str
    collection_id: str
    user_id: str
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WikiPageListResponse(BaseModel):
    items: List[Any] = Field(default_factory=list, description="List of WikiPage objects")
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


class WikiGraphData(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, str]] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class WikiStats(BaseModel):
    total_pages: int = 0
    pages_by_type: Dict[str, int] = Field(default_factory=dict)
    total_links: int = 0
    orphan_count: int = 0
    recent_updates: List[WikiPage] = Field(default_factory=list)
    pending_tasks: int = 0
    pending_issues: int = 0
    is_active: bool = False


class WikiIndexGroup(BaseModel):
    type: str
    total: int = 0
    items: List[Dict[str, str]] = Field(default_factory=list)


class WikiIndexResponse(BaseModel):
    intro: str = ""
    version: int = 1
    groups: List[WikiIndexGroup] = Field(default_factory=list)


class WikiPageSearchResult(BaseModel):
    slug: str
    title: str
    summary: str = ""


class WikiLogEntry(BaseModel):
    id: int
    collection_id: str
    action: str
    collection_ref: Optional[str] = None
    doc_title: Optional[str] = None
    summary: Optional[str] = None
    pages_affected: List[Dict[str, str]] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class WikiLogListResponse(BaseModel):
    entries: List[Any] = Field(default_factory=list)
    next_cursor: Optional[str] = None


class WikiIssueCreate(BaseModel):
    slug: str
    issue_type: str
    description: str
    reported_by: str = "user"
    suspected_ids: Optional[List[str]] = None


class WikiIssue(BaseModel):
    id: str
    collection_id: str
    slug: str
    issue_type: str
    description: str
    status: str = "pending"
    reported_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
