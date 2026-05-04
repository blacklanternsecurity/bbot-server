from typing import Annotated, Optional

from pydantic import Field, computed_field

from bbot_server.models.base import AssetQuery, BaseScore, BaseAssetFacet

# Severity levels as constants
SEVERITY_LEVELS = {"INFO": 1, "LOW": 2, "MEDIUM": 3, "HIGH": 4, "CRITICAL": 5}

# Confidence levels as constants
CONFIDENCE_LEVELS = {"UNKNOWN": 1, "LOW": 2, "MEDIUM": 3, "HIGH": 4, "CONFIRMED": 5}

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


class FindingsQuery(AssetQuery):
    """Base request body for findings query/count endpoints."""

    min_severity: int = Field(1, description="Filter by minimum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)
    max_severity: int = Field(5, description="Filter by maximum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)
    ignored: bool | None = Field(None, description="Filter by ignored status")
    _force_asset_type = "Finding"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Validate severity range
        if self.min_severity > self.max_severity:
            from bbot_server.errors import BBOTServerValueError

            raise BBOTServerValueError("min_severity must be less than or equal to max_severity")

    async def build(self, applet=None):
        query = await super().build(applet)

        # severity filtering
        if "severity_score" not in query and (self.min_severity != 1 or self.max_severity != 5):
            query["severity_score"] = {}
            if self.min_severity != 1:
                query["severity_score"]["$gte"] = self.min_severity
            if self.max_severity != 5:
                query["severity_score"]["$lte"] = self.max_severity

        # ignored filtering
        if self.ignored is not None and "ignored" not in query:
            query["ignored"] = self.ignored

        return query


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
