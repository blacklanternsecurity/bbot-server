import uuid
import unicodedata
from typing import Optional
from typing import Annotated
from pydantic import UUID4, Field

from bbot.scanner.target import BBOTTarget
from bbot_server.utils.misc import utc_now
from bbot_server.models.base import BaseBBOTServerModel


class BaseTarget(BaseBBOTServerModel):
    description: str = ""
    seeds: list[str] = []
    whitelist: Optional[list[str]] = None
    blacklist: list[str] = []
    strict_dns_scope: bool = False
    hash: Annotated[str, "indexed", "unique"] = ""
    scope_hash: Annotated[str, "indexed"] = ""
    seed_hash: Annotated[str, "indexed"] = ""
    whitelist_hash: Annotated[str, "indexed"] = ""
    blacklist_hash: Annotated[str, "indexed"] = ""
    seed_size: int = 0
    whitelist_size: int = 0
    blacklist_size: int = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seeds = self._clean_scope_list(self.seeds)
        self.whitelist = None if self.whitelist is None else self._clean_scope_list(self.whitelist)
        self.blacklist = self._clean_scope_list(self.blacklist)
        self._bbot_target = BBOTTarget(
            *self.seeds, whitelist=self.whitelist, blacklist=self.blacklist, strict_dns_scope=self.strict_dns_scope
        )
        self.hash = self.bbot_target.hash.hex()
        self.scope_hash = self.bbot_target.scope_hash.hex()
        self.seed_hash = self.bbot_target.seeds.hash.hex()
        self.whitelist_hash = self.bbot_target.whitelist.hash.hex()
        self.blacklist_hash = self.bbot_target.blacklist.hash.hex()
        self.seed_size = len(self.bbot_target.seeds)
        self.whitelist_size = 0 if not self.bbot_target._orig_whitelist else len(self.bbot_target.whitelist)
        self.blacklist_size = len(self.bbot_target.blacklist)

    @property
    def bbot_target(self):
        return self._bbot_target

    @staticmethod
    def _strip_invisible_characters(value: str) -> str:
        """
        Remove zero-width and other non-printable formatting characters from a string.
        """

        return "".join(ch for ch in value if unicodedata.category(ch) != "Cf").strip()

    @classmethod
    def _normalize_scope_entry(cls, value: str) -> str:
        """
        Normalize a single scope entry.

        - Remove invisible characters.
        - Strip whitespace.
        - Drop leading dots (commonly used to denote a suffix match like ".gr").
        """

        cleaned = cls._strip_invisible_characters(value)

        # Users sometimes prefix a dot to indicate a suffix match (e.g. ".example.com").
        # BBOTTarget expects a bare host, so strip the prefix to keep the value valid.
        if cleaned.startswith("."):
            cleaned = cleaned.lstrip(".")

        return cleaned

    @classmethod
    def _clean_scope_list(cls, entries: list[str]) -> list[str]:
        """
        Clean scope lists (seeds/whitelist/blacklist) to avoid invalid host errors.

        - Remove invisible formatting characters that can sneak in during copy/paste.
        - Strip surrounding whitespace.
        - Drop empty values after cleaning.
        """

        return [cleaned for value in entries if (cleaned := cls._normalize_scope_entry(value))]


class Target(BaseTarget):
    __tablename__ = "targets"
    __user__ = True
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    name: Annotated[str, "indexed", "unique"]
    default: Annotated[bool, "indexed"] = False
    created: Annotated[float, "indexed"] = Field(default_factory=utc_now)
    modified: Annotated[float, "indexed"] = Field(default_factory=utc_now)
