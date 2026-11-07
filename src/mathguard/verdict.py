"""Result types shared by all checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    """How strongly a claim has been confirmed.

    The names are deliberately honest: only ``VERIFIED`` means a computer
    algebra system reduced the claim to an identity. ``LIKELY`` means many
    random numerical tests passed, which is strong evidence but not a proof.
    """

    VERIFIED = "verified"          # confirmed symbolically by the CAS
    LIKELY = "likely"              # passed numerical testing, no symbolic proof
    REFUTED = "refuted"            # a concrete counterexample or contradiction was found
    INCONCLUSIVE = "inconclusive"  # could not decide either way
    ERROR = "error"                # the input could not be parsed or evaluated

    @property
    def ok(self) -> bool:
        return self in (Status.VERIFIED, Status.LIKELY)


# Order used to combine several verdicts into one overall status (worst wins).
_SEVERITY = {
    Status.VERIFIED: 0,
    Status.LIKELY: 1,
    Status.INCONCLUSIVE: 2,
    Status.ERROR: 3,
    Status.REFUTED: 4,
}


def worst(statuses: list[Status]) -> Status:
    if not statuses:
        return Status.INCONCLUSIVE
    return max(statuses, key=lambda s: _SEVERITY[s])


@dataclass
class Verdict:
    """Outcome of a single check."""

    check: str
    status: Status
    message: str
    method: str | None = None
    counterexample: dict[str, Any] | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status.ok

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return {k: v for k, v in d.items() if v not in (None, {}, [])}

    def __str__(self) -> str:
        icon = {
            Status.VERIFIED: "✔",
            Status.LIKELY: "≈",
            Status.REFUTED: "✘",
            Status.INCONCLUSIVE: "?",
            Status.ERROR: "!",
        }[self.status]
        text = f"{icon} [{self.status.value}] {self.check}: {self.message}"
        if self.counterexample:
            pairs = ", ".join(f"{k} = {v}" for k, v in self.counterexample.items())
            text += f"\n    counterexample: {pairs}"
        return text


@dataclass
class Report:
    """Several verdicts plus the combined status."""

    verdicts: list[Verdict]

    @property
    def status(self) -> Status:
        return worst([v.status for v in self.verdicts])

    @property
    def ok(self) -> bool:
        return self.status.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "ok": self.ok,
            "results": [v.to_dict() for v in self.verdicts],
        }

    def __str__(self) -> str:
        lines = [str(v) for v in self.verdicts]
        lines.append(f"\nOverall: {self.status.value.upper()}")
        return "\n".join(lines)
