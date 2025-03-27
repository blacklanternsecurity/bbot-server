from bbot_server.config import BBOT_SERVER_URL
from bbot_server.cli.base import BaseBBCTL, subcommand, Option, Annotated


class Agent(BaseBBCTL):
    command = "agent"
    help = "Manage BBOT agents"
    epilog = "Create or start a BBOT server agent. An agent runs BBOT scans, and reports results back to the server."

    @subcommand(help="Create a new agent")
    def create(
        self,
        name: Annotated[str, Option("--name", "-n", help="Name of the agent", metavar="NAME")],
    ):
        agent = self.bbot_server.create_agent(name=name)
        print(agent.model_dump_json())

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
