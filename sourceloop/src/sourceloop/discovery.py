"""Provider-neutral contact discovery and normalization.

The built-in providers only consume customer-supplied or connector-supplied
records. They do not scrape private profiles, guess personal addresses, or
silently convert unverified search results into outreach targets. External
search, registry, CRM, and marketplace integrations implement the same
``DiscoveryProvider`` protocol and return provenance with every candidate.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .domain import CaseRecord, ContactRoute, GeoPoint
from .packs import VerticalPack

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PERSONAL_PROVIDER_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}


class DiscoveryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_name: str
    role_title: str = "Public business contact"
    endpoint: str
    source: str
    source_public: bool = True
    confidence: float = Field(default=0.65, ge=0, le=1)
    geography: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    topics: list[str] = Field(default_factory=list)
    legal_name: str | None = None
    license_number: str | None = None
    registry_id: str | None = None
    endpoint_type: str = "role_or_business_inbox"
    evidence: list[str] = Field(default_factory=list)


class DiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contacts: list[ContactRoute] = Field(default_factory=list)
    rejected: list[dict[str, Any]] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)


class DiscoveryProvider(Protocol):
    name: str

    def discover(self, case: CaseRecord, pack: VerticalPack | None) -> list[DiscoveryCandidate]: ...


class RequirementSeedDiscovery:
    """Read candidates inserted by an approved connector or an operator."""

    name = "requirement_seed"

    def discover(self, case: CaseRecord, pack: VerticalPack | None) -> list[DiscoveryCandidate]:
        raw = case.requirements.get("discovery_candidates", [])
        if not isinstance(raw, list):
            return []
        results: list[DiscoveryCandidate] = []
        for value in raw:
            if not isinstance(value, dict):
                continue
            payload = dict(value)
            payload.setdefault("source", "case.requirements.discovery_candidates")
            payload.setdefault("geography", _case_geography(case))
            payload.setdefault("topics", [pack.category if pack else case.kind.value])
            try:
                results.append(DiscoveryCandidate.model_validate(payload))
            except ValueError:
                continue
        return results


class RegistryResultDiscovery:
    """Read organization/contact records returned by an authoritative connector."""

    name = "registry_result"

    def discover(self, case: CaseRecord, pack: VerticalPack | None) -> list[DiscoveryCandidate]:
        registry = case.requirements.get("registry_results", {})
        if not isinstance(registry, dict):
            return []
        raw = registry.get("organizations", [])
        if not isinstance(raw, list):
            return []
        results: list[DiscoveryCandidate] = []
        for value in raw:
            if not isinstance(value, dict) or not value.get("endpoint"):
                continue
            payload = {
                "organization_name": value.get("organization_name") or value.get("name") or "Registry organization",
                "role_title": value.get("role_title") or "Public registry contact",
                "endpoint": value["endpoint"],
                "source": value.get("source") or "case.registry_results",
                "source_public": bool(value.get("source_public", True)),
                "confidence": float(value.get("confidence", 0.85)),
                "geography": value.get("geography") or _case_geography(case),
                "latitude": value.get("latitude"),
                "longitude": value.get("longitude"),
                "topics": value.get("topics") or [pack.category if pack else case.kind.value],
                "legal_name": value.get("legal_name"),
                "license_number": value.get("license_number"),
                "registry_id": value.get("registry_id"),
                "endpoint_type": value.get("endpoint_type", "public_registry_inbox"),
                "evidence": value.get("evidence") or [],
            }
            try:
                results.append(DiscoveryCandidate.model_validate(payload))
            except ValueError:
                continue
        return results


class ContactDiscoveryService:
    def __init__(self, providers: list[DiscoveryProvider] | None = None) -> None:
        self.providers = providers or [RegistryResultDiscovery(), RequirementSeedDiscovery()]

    def discover(self, case: CaseRecord, pack: VerticalPack | None) -> DiscoveryResult:
        accepted: dict[str, ContactRoute] = {}
        rejected: list[dict[str, Any]] = []
        provider_names: list[str] = []
        for provider in self.providers:
            provider_names.append(provider.name)
            for candidate in provider.discover(case, pack):
                reason = _rejection_reason(candidate, case)
                if reason:
                    rejected.append(
                        {
                            "endpoint": candidate.endpoint,
                            "organization_name": candidate.organization_name,
                            "source": candidate.source,
                            "reason": reason,
                        }
                    )
                    continue
                endpoint = candidate.endpoint.strip().lower()
                location = None
                if candidate.latitude is not None and candidate.longitude is not None:
                    location = GeoPoint(
                        latitude=candidate.latitude,
                        longitude=candidate.longitude,
                        label=candidate.organization_name,
                        precision="public_business_location",
                    )
                route = ContactRoute(
                    organization_name=candidate.organization_name.strip(),
                    role_title=candidate.role_title.strip() or "Public business contact",
                    endpoint=endpoint,
                    source=candidate.source,
                    source_public=candidate.source_public,
                    confidence=candidate.confidence,
                    geography=candidate.geography,
                    location=location,
                    topics=candidate.topics,
                    legal_name=candidate.legal_name,
                    license_number=candidate.license_number,
                    registry_id=candidate.registry_id,
                )
                existing = accepted.get(endpoint)
                if existing is None or route.confidence > existing.confidence:
                    accepted[endpoint] = route

        contacts = sorted(
            accepted.values(),
            key=lambda route: (-route.confidence, route.organization_name.lower(), route.endpoint),
        )[: case.max_contacts]
        return DiscoveryResult(contacts=contacts, rejected=rejected, providers=provider_names)


def _rejection_reason(candidate: DiscoveryCandidate, case: CaseRecord) -> str | None:
    endpoint = candidate.endpoint.strip().lower()
    if not candidate.source_public:
        return "The endpoint was not identified as a public or authorized business contact."
    if not _EMAIL_RE.match(endpoint):
        return "The endpoint is not a syntactically valid email address."
    if candidate.endpoint_type in {"private_personal", "private_profile", "guessed_email"}:
        return "Private, profile-derived, or guessed endpoints are not eligible for outreach."
    domain = endpoint.rsplit("@", 1)[-1]
    if domain in _PERSONAL_PROVIDER_DOMAINS and candidate.endpoint_type not in {
        "public_role_inbox",
        "published_business_inbox",
    }:
        return "A personal-provider address requires evidence that it was intentionally published for business inquiries."
    if not candidate.organization_name.strip():
        return "An accountable organization or business name is required."
    if candidate.confidence < 0.45:
        return "Candidate confidence is below the outreach threshold."
    if case.risk_tier.value in {"high", "restricted"} and not candidate.evidence:
        return "High-risk candidates require an evidence reference for the public contact route."
    return None


def _case_geography(case: CaseRecord) -> str | None:
    value = case.requirements.get("geography") or case.requirements.get("state")
    if value:
        return str(value)
    return case.location.label if case.location else None
