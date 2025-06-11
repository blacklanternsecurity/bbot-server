from pydantic import Field, computed_field
from typing import Annotated, Optional, Union

from bbot_server.models.asset_models import BaseAssetFacet

# Severity levels as constants
SEVERITY_LEVELS = {"INFO": 1, "LOW": 2, "MEDIUM": 3, "HIGH": 4, "CRITICAL": 5}

# severity colors for rich, etc. (bash color names)
SEVERITY_COLORS = {
    1: "deep_sky_blue1",  # INFO = blue
    2: "gold1",  # LOW = yellow
    3: "dark_orange",  # MEDIUM = orange
    4: "bright_red",  # HIGH = red
    5: "purple",  # CRITICAL = purple
}


class SeverityScore:
    """Maps severity levels to numeric scores and provides conversion methods."""

    @classmethod
    def to_score(cls, severity: Union[str, int]) -> int:
        """Convert a severity level to its numeric score."""
        if isinstance(severity, int):
            if severity not in SEVERITY_LEVELS.values():
                raise ValueError(f"Invalid severity score: {severity}. Must be between 1 and 5.")
            return severity
        if isinstance(severity, str):
            severity = severity.upper()
            if severity not in SEVERITY_LEVELS:
                raise ValueError(f"Invalid severity string: {severity}. Must be one of {list(SEVERITY_LEVELS.keys())}")
            return SEVERITY_LEVELS[severity]

    @classmethod
    def to_severity(cls, score: int) -> str:
        """Convert a numeric score to its string equivalent."""
        for level, value in SEVERITY_LEVELS.items():
            if value == score:
                return level
        raise ValueError(f"Invalid severity score: {score}. Must be between 1 and 5.")


class Finding(BaseAssetFacet):
    name: Annotated[str, "indexed", "indexed-text"]
    description: Annotated[str, "indexed-text"]
    verified: Annotated[bool, "indexed"] = False
    severity_score: Annotated[int, "indexed"] = Field(
        description="Numeric severity score of the vulnerability (1-5)",
        ge=1,
        le=5,
    )
    confidence: Annotated[int, "indexed"] = Field(
        description="Confidence level of the vulnerability (1-5)",
        ge=1,
        le=5,
        default=1,
    )
    temptation: Optional[Annotated[int, "indexed"]] = Field(
        description="Likelihood of an attacker taking interest in this finding (1-5)",
        ge=1,
        le=5,
        default=None,
    )
    cves: Optional[Annotated[list[str], "indexed"]] = Field(
        description="List of associated CVEs",
        default=None,
    )

    def __init__(self, **kwargs):
        # convert severity to severity_score
        severity = kwargs.pop("severity", None)
        if severity is not None:
            kwargs["severity_score"] = SeverityScore.to_score(severity)
        super().__init__(**kwargs)

    @computed_field
    @property
    def severity(self) -> str:
        """
        The string version of the severity score, e.g. 3 -> "MEDIUM", 4 -> "HIGH", etc.
        """
        return SeverityScore.to_severity(self.severity_score)

    @computed_field
    @property
    def id(self) -> Annotated[str, "indexed"]:
        """
        The unique ID of the finding is the hash of the description and netloc.
        """
        return self.sha1(f"{self.description}:{self.netloc}")
