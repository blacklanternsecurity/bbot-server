from typing import Union
from sqlmodel import Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import Field as PydanticField, computed_field

from bbot.core.helpers.misc import make_netloc

from bbot_server.models.base import BaseHostModel, AssetQuery, BaseScore, derive
from bbot_server.utils.misc import utc_now

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


class FindingsQuery(AssetQuery):
    """Base request body for findings query/count endpoints."""

    min_severity: int = PydanticField(1, description="Filter by minimum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)
    max_severity: int = PydanticField(5, description="Filter by maximum severity (1=INFO, 5=CRITICAL)", ge=1, le=5)
    ignored: bool | None = PydanticField(None, description="Filter by ignored status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.min_severity > self.max_severity:
            from bbot_server.errors import BBOTServerValueError
            raise BBOTServerValueError("min_severity must be less than or equal to max_severity")

    async def build(self, applet=None):
        stmt = await super().build(applet)
        model = self._applet.model

        # severity filtering
        if self.min_severity != 1:
            stmt = stmt.where(model.severity_score >= self.min_severity)
        if self.max_severity != 5:
            stmt = stmt.where(model.severity_score <= self.max_severity)

        # ignored filtering
        if self.ignored is not None:
            stmt = stmt.where(model.ignored == self.ignored)

        return stmt

    async def _apply_search(self, stmt, model):
        """Search across host, name, and description for findings."""
        from sqlalchemy import or_

        search_str = self.search.strip().lower()
        if not search_str:
            return stmt
        conditions = [
            model.host.ilike(f"%{search_str}%"),
            model.name.ilike(f"%{search_str}%"),
            model.description.ilike(f"%{search_str}%"),
        ]
        stmt = stmt.where(or_(*conditions))
        return stmt


class Finding(BaseHostModel, table=True):
    __tablename__ = "findings"

    pk: int | None = Field(default=None, primary_key=True)
    id: str | None = Field(default=None, index=True, sa_column_kwargs={"unique": True})
    name: str = Field(index=True)
    description: str = ""
    verified: bool = Field(default=False, index=True)
    severity_score: int = Field(ge=1, le=5, index=True)
    confidence_score: int = Field(ge=1, le=5, default=1)
    temptation: int | None = Field(default=None)
    cves: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))

    def __init__(self, **kwargs):
        # convert severity/confidence strings to scores
        severity = kwargs.pop("severity", None)
        if severity is not None:
            kwargs["severity_score"] = SeverityScore.to_score(severity)
        confidence = kwargs.pop("confidence", None)
        if confidence is not None:
            kwargs["confidence_score"] = ConfidenceScore.to_score(confidence)
        super().__init__(**kwargs)

    @derive("id")
    def _derive_id(self):
        if self.description and self.netloc:
            return self.sha1(f"{self.description}:{self.netloc}")

    @computed_field
    @property
    def severity(self) -> str:
        return SeverityScore.to_str(self.severity_score)

    @computed_field
    @property
    def confidence(self) -> str:
        return ConfidenceScore.to_str(self.confidence_score)

    @computed_field
    @property
    def type(self) -> str:
        return "Finding"
