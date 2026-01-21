from typing import Annotated, Optional

from bbot.models.pydantic import BBOTBaseModel
from fastapi import Body
from pydantic import Field, computed_field

from bbot_server.models.base import BaseScore, QueryRequestBody, BaseRequestBody
from bbot_server.models.asset_models import BaseAssetFacet

# Severity levels as constants
SEVERITY_LEVELS = {"INFO": 1, "LOW": 2, "MEDIUM": 3, "HIGH": 4, "CRITICAL": 5}

# Confidence levels as constants
CONFIDENCE_LEVELS = {"UNKNOWN": 1, "LOW": 2, "MODERATE": 3, "HIGH": 4, "CONFIRMED": 5}

# severity colors for rich, etc. (bash color names)
SEVERITY_COLORS = {
    1: "deep_sky_blue1",  # INFO = blue
    2: "gold1",  # LOW = yellow
    3: "dark_orange",  # MEDIUM = orange
    4: "bright_red",  # HIGH = red
    5: "purple",  # CRITICAL = purple
}


class SeverityScore(BaseScore):
    """Maps severity levels to numeric scores and provides conversion methods."""

    levels = SEVERITY_LEVELS
    name = "severity"


class ConfidenceScore(BaseScore):
    """Maps confidence levels to numeric scores and provides conversion methods."""

    levels = CONFIDENCE_LEVELS
    name = "confidence"


class BaseFindingsRequestBody(BBOTBaseModel):
    host: Annotated[str | None, Body(description="Filter by exact hostname or IP address")] = None
    domain: Annotated[str | None, Body(description="Filter by domain or subdomain")] = None
    target_id: Annotated[str | None, Body(description="Filter by target name or id")] = None
    archived: Annotated[bool, Body(description="Whether to include archived findings")] = False
    active: Annotated[bool, Body(description="Whether to include active (non-archived) findings")] = True
    ignored: Annotated[bool, Body(description="Filter on whether the finding is ignored")] = False
    min_severity: Annotated[int, Body(description="Filter by minimum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)] = 1
    max_severity: Annotated[int, Body(description="Filter by maximum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)] = 5


class QueryFindingsRequestBody(BaseFindingsRequestBody, QueryRequestBody):
    pass


class CountFindingsRequestBody(BaseFindingsRequestBody, BaseRequestBody):
    pass


class Finding(BaseAssetFacet):
    name: Annotated[str, "indexed", "indexed-text"]
    description: Annotated[str, "indexed-text"]
    verified: Annotated[bool, "indexed"] = False
    severity_score: Annotated[int, "indexed"] = Field(
        description="Numeric severity score of the vulnerability (1-5)",
        ge=1,
        le=5,
    )
    confidence_score: Annotated[int, "indexed"] = Field(
        description="Numeric confidence score of the vulnerability (1-5)",
        ge=1,
        le=5,
        default=1,
        alias="confidence",
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
        # convert confidence to confidence_score
        confidence = kwargs.pop("confidence", None)
        if confidence is not None:
            kwargs["confidence_score"] = ConfidenceScore.to_score(confidence)
        super().__init__(**kwargs)

    @computed_field
    @property
    def severity(self) -> str:
        """
        The string version of the severity score, e.g. 3 -> "MEDIUM", 4 -> "HIGH", etc.
        """
        return SeverityScore.to_str(self.severity_score)

    @computed_field
    @property
    def confidence(self) -> str:
        """
        The string version of the confidence score, e.g. 1 -> "UNKNOWN", 5 -> "CONFIRMED", etc.
        """
        return ConfidenceScore.to_str(self.confidence_score)

    @computed_field
    @property
    def id(self) -> Annotated[str, "indexed", "unique"]:
        """
        The unique ID of the finding is the hash of the description and netloc.
        """
        return self.sha1(f"{self.description}:{self.netloc}")
