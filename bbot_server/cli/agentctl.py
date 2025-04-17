from datetime import datetime

from bbot_server.cli import common
from bbot_server.cli.base import BaseBBCTL, subcommand, Option, Annotated


class AgentCTL(BaseBBCTL):
    command = "agent"
    help = "Create or start a BBOT server agent. An agent runs BBOT scans, and reports results back to the server."
    short_help = "Manage BBOT agents"

    @subcommand(help="Create a new agent")
    def create(
        self,
        name: Annotated[str, Option("--name", "-n", help="Name of the agent", metavar="NAME")],
        description: Annotated[
            str, Option("--description", "-d", help="Description of the agent", metavar="DESCRIPTION")
        ] = "",
    ):
        agent = self.bbot_server.create_agent(name=name, description=description)
        print(agent.model_dump_json())

    @subcommand(help="List all agents")
    def list(
        self,
        json: common.json = False,
        csv: common.csv = False,
    ):
        agents = self.bbot_server.get_agents()

        if json:
            for agent in agents:
                self.sys.stdout.buffer.write(self.orjson.dumps(agent.model_dump()))
            return

        if csv:
            for line in common.json_to_csv(agents, fieldnames=["name", "status", "last_seen", "id"]):
                self.sys.stdout.buffer.write(line)
            return

        table = self.Table()
        table.add_column("Name", style=self.COLOR)
        table.add_column("Status")
        table.add_column("Last Seen")
        table.add_column("ID", style=self.DARK_COLOR)
        for agent in agents:
            last_seen = (
                datetime.fromtimestamp(agent.last_seen).strftime("%Y-%m-%d %H:%M:%S") if agent.last_seen else "never"
            )
            table.add_row(agent.name, agent.status, last_seen, str(agent.id))
        self.stdout.print(table)

    @subcommand(help="Delete an agent")
    def delete(
        self,
        agent_id: Annotated[str, Option("--id", "-i", help="ID of the agent to delete", metavar="UUID")] = None,
        agent_name: Annotated[
            str, Option("--name", "-n", help="Name of the agent to delete", metavar="STRING")
        ] = None,
    ):
        if agent_id is None and agent_name is None:
            raise self.BBOTServerValueError("Either --id or --name must be provided")
        self.bbot_server.delete_agent(id=agent_id, name=agent_name)

    @subcommand(help="Start an agent process")
    def start(
        self,
        agent_id: Annotated[str, Option("--id", "-i", help="ID of the agent to start", metavar="UUID")],
        agent_name: Annotated[str, Option("--name", "-n", help="Name of the agent", metavar="STRING")],
    ):
        print("Starting BBOT agent")

        from bbot_server.agent import BBOTAgent

        agent = BBOTAgent(agent_id, agent_name, self.root.config, synchronous=True)
        try:
            self.log.info("Starting agent")
            agent.loop()
        finally:
            self.log.info("Stopping agent")
            agent.stop()
