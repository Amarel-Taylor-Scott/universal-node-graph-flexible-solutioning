"""Opt-in runtime payload validation for content-addressed ``ValueType`` schemas.

The compiler proves nominal schema identity.  This module supplies the separate
runtime seam that can validate actual values when an authorized validator for
that exact schema digest and media type is registered.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from solutiongraph.model import DIGEST_RE, ID_RE, ValueType, sha256_digest


class PayloadValidator(Protocol):
    identifier: str
    schema_digest: str
    media_type: str
    implementation_digest: str

    def validate(self, value: Any) -> Sequence[str]: ...


class PayloadValidationError(ValueError):
    """Stable runtime validation failure with a receiptable failure class."""

    def __init__(
        self,
        failure_class: str,
        path: str,
        problems: Sequence[str],
    ) -> None:
        self.failure_class = failure_class
        self.path = path
        self.problems = tuple(problems)
        detail = "; ".join(self.problems) if self.problems else "validation failed"
        super().__init__(f"{path}: {detail}")


@dataclass(frozen=True)
class CallablePayloadValidator:
    """Content-identified validator backed by a trusted local callable."""

    identifier: str
    schema_digest: str
    function: Callable[[Any], Sequence[str]]
    media_type: str = "application/json"
    implementation_digest: str = ""

    def __post_init__(self) -> None:
        if not self.implementation_digest:
            object.__setattr__(
                self,
                "implementation_digest",
                sha256_digest(inspect.getsource(self.function)),
            )

    def problems(self) -> list[str]:
        problems: list[str] = []
        if not ID_RE.fullmatch(self.identifier):
            problems.append("payload validator identifier must be namespaced")
        if not DIGEST_RE.fullmatch(self.schema_digest):
            problems.append("payload validator schema_digest must be sha256")
        if not DIGEST_RE.fullmatch(self.implementation_digest):
            problems.append("payload validator implementation_digest must be sha256")
        if not self.media_type.strip():
            problems.append("payload validator media_type must not be empty")
        if not callable(self.function):
            problems.append("payload validator function must be callable")
        return problems

    def validate(self, value: Any) -> Sequence[str]:
        result = self.function(value)
        if isinstance(result, (str, bytes)) or not isinstance(result, Sequence):
            raise TypeError("payload validator must return a sequence of problem strings")
        if any(not isinstance(item, str) or not item.strip() for item in result):
            raise TypeError("payload validator problems must be nonempty strings")
        return tuple(result)

    def identity_record(self) -> dict[str, str]:
        return {
            "identifier": self.identifier,
            "schema_digest": self.schema_digest,
            "media_type": self.media_type,
            "implementation_digest": self.implementation_digest,
        }


class PayloadValidatorRegistry:
    """Exact schema/media-type dispatch with an optional fail-closed mode."""

    def __init__(
        self,
        validators: Sequence[PayloadValidator] = (),
        *,
        require_registered: bool = False,
    ) -> None:
        self.require_registered = require_registered
        self._validators: dict[tuple[str, str], PayloadValidator] = {}
        problems: list[str] = []
        for index, validator in enumerate(validators):
            validator_problems = getattr(validator, "problems", lambda: [])()
            problems.extend(f"validators[{index}]: {item}" for item in validator_problems)
            key = (validator.schema_digest, validator.media_type)
            if key in self._validators:
                problems.append(
                    "payload validators must be unique by schema digest and media type"
                )
            self._validators[key] = validator
        if problems:
            raise ValueError("invalid payload validator registry: " + "; ".join(problems))

    def identity_records(self) -> tuple[dict[str, str], ...]:
        return tuple(
            {
                "identifier": validator.identifier,
                "schema_digest": validator.schema_digest,
                "media_type": validator.media_type,
                "implementation_digest": validator.implementation_digest,
            }
            for _, validator in sorted(self._validators.items())
        )

    def identity_record(self) -> dict[str, Any]:
        """Return every setting that can change payload-validation behavior."""

        return {
            "require_registered": self.require_registered,
            "validators": list(self.identity_records()),
        }

    def validate_value(self, value_type: ValueType, value: Any, *, path: str) -> None:
        if not value_type.schema_digest:
            return
        validator = self._validators.get(
            (value_type.schema_digest, value_type.media_type)
        )
        if validator is None:
            if self.require_registered:
                raise PayloadValidationError(
                    "runtime.schema-validator-missing",
                    path,
                    (
                        f"no validator registered for {value_type.schema_digest} "
                        f"and {value_type.media_type}",
                    ),
                )
            return
        try:
            problems = tuple(validator.validate(value))
        except PayloadValidationError:
            raise
        except Exception as exc:
            raise PayloadValidationError(
                "runtime.schema-validator-error",
                path,
                (f"{validator.identifier} raised {type(exc).__name__}: {exc}",),
            ) from exc
        if problems:
            raise PayloadValidationError("runtime.schema-invalid", path, problems)


__all__ = [
    "CallablePayloadValidator",
    "PayloadValidationError",
    "PayloadValidator",
    "PayloadValidatorRegistry",
]
