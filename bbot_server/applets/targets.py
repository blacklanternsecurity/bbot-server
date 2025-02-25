import uuid
from pydantic import UUID4, Field
from typing import Annotated, Union
from bbot_server.models.base import BaseBBOTServerModel

from bbot_server.applets._base import BaseApplet, api_endpoint


class Target(BaseBBOTServerModel):
    __tablename__ = "targets"

    name: Annotated[str, "indexed", "unique"]
    id: Annotated[UUID4, "indexed", "unique"] = Field(default_factory=uuid.uuid4)
    description: str = ""
    target: list[str] = []
    whitelist: Union[list[str], None] = None
    blacklist: Union[list[str], None] = None


class TargetsApplet(BaseApplet):
    name = "Targets"
    description = "scan targets"
    model = Target

    @api_endpoint("/", methods=["GET"], summary="Get a single scan target by its name or id")
    async def get_target(self, name: str = "", id: UUID4 = None) -> Target:
        if (not name) and (not id):
            raise self.BBOTValueError("Either name or id must be provided")
        query = {}
        if name:
            query["name"] = name
        elif id is not None:
            query["id"] = str(id)
        target = await self.collection.find_one(query)
        if target is None:
            return
        return Target(**target)

    @api_endpoint("/create", methods=["POST"], summary="Create a new scan target")
    async def create_target(
        self,
        name: str,
        description: str = "",
        target: list[str] = [],
        whitelist: list[str] = [],
        blacklist: list[str] = [],
    ) -> Target:
        target = Target(name=name, description=description, target=target, whitelist=whitelist, blacklist=blacklist)
        await self.collection.insert_one(target.model_dump())
        return target

    @api_endpoint("/{id}", methods=["PATCH"], summary="Update a scan target by its id")
    async def update_target(self, id: UUID4, target: Target) -> Target:
        target.id = id
        await self.collection.update_one({"id": str(id)}, {"$set": target.model_dump()})
        return target

    @api_endpoint("/{id}", methods=["DELETE"], summary="Delete a scan target by its id")
    async def delete_target(self, id: UUID4) -> None:
        # TODO: check if target is used in any scans
        await self.collection.delete_one({"id": str(id)})

    @api_endpoint("/list", methods=["GET"], summary="List scans")
    async def get_targets(self) -> list[Target]:
        cursor = self.collection.find()
        targets = await cursor.to_list(length=None)
        targets = [Target(**target) for target in targets]
        return targets
