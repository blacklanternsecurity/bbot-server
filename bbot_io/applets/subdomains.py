from sqlmodel import distinct, func, select
from bbot_io.applets.base import BaseApplet, api_endpoint


class Subdomains(BaseApplet):

    nested = False

    @api_endpoint("/", methods=["GET"], summary="Get Subdomains")
    async def get_subdomains(self, in_scope_only: bool = True) -> list[str]:
        statement = select(distinct(self.model.host)).where(self.model.type == "DNS_NAME")
        if in_scope_only:
            statement = statement.where(self.model.scope_distance == 0)
        return await self.db.exec(statement)

    @api_endpoint("/summary", methods=["GET"], summary="Get Subdomains Summary")
    async def get_subdomain_summary(self) -> list[str]:
        statement = (
            select(self.model.host, self.model.type, func.count(self.model.id).label("count"))
            .where(self.model.host.is_not(None))
            .group_by(self.model.host, self.model.type)
        )
        results = await self.db.exec(statement)
        result_dict = {}
        for host, _type, count in results:
            try:
                result_dict[host][_type] = count
            except KeyError:
                result_dict[host] = {_type: count}
        return result_dict
