import asyncio

from tests.test_applets.base import BaseAppletTest
from bbot_server.applets._base import BaseApplet, watchdog_task


class ScheduledTaskApplet(BaseApplet):
    name = "Scheduled Tasks"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cron_task_ran = False
        self.cron_task_2_ran = False
        self.cron_task_3_ran = False

    @watchdog_task(cron="* * * * *")
    async def cron_task(self):
        self.log.critical("cron_task ran")
        self.cron_task_ran = True

    @watchdog_task(cron="* * * * *", cron_config_key="test.cron_task_2")
    async def cron_task_2(self):
        self.log.critical("cron_task_2 ran")
        self.cron_task_2_ran = True

    @watchdog_task(cron="* * * * *", cron_config_key="test.cron_task_3")
    async def cron_task_3(self):
        self.log.critical("cron_task_3 ran")
        self.cron_task_3_ran = True


class TestScheduledTasks(BaseAppletTest):
    config_overrides = {"test": {"cron_task_2": "*/1 * * * *"}}

    async def setup(self):
        self.bbot_server.include_app(ScheduledTaskApplet)
        await self.bbot_server.scheduled_tasks._setup()

        assert self.bbot_server.scheduled_tasks.cron_task_ran is False, "cron_task ran before setup"
        assert self.bbot_server.scheduled_tasks.cron_task_2_ran is False, "cron_task_2 ran before setup"
        assert self.bbot_server.scheduled_tasks.cron_task_3_ran is False, "cron_task_3 ran before setup"

        all_tasks = self.bbot_server.task_broker.get_all_tasks()

        for task_name, task in all_tasks.items():
            self.log.critical(f"{task_name}: {task.labels}")

        assert "tests.test_scheduled_tasks:cron_task" in all_tasks, "cron_task is not registered"
        assert "tests.test_scheduled_tasks:cron_task_2" in all_tasks, "cron_task_2 is not registered"
        assert "tests.test_scheduled_tasks:cron_task_3" in all_tasks, "cron_task_3 is not registered"

        assert all_tasks["tests.test_scheduled_tasks:cron_task"].labels == {"schedule": [{"cron": "* * * * *"}]}
        assert all_tasks["tests.test_scheduled_tasks:cron_task_2"].labels == {"schedule": [{"cron": "*/1 * * * *"}]}
        assert all_tasks["tests.test_scheduled_tasks:cron_task_3"].labels == {"schedule": [{"cron": "* * * * *"}]}

        # wait for cron tasks to run
        for i in range(60 * 10):
            if all(
                [
                    self.bbot_server.scheduled_tasks.cron_task_ran,
                    self.bbot_server.scheduled_tasks.cron_task_2_ran,
                    self.bbot_server.scheduled_tasks.cron_task_3_ran,
                ]
            ):
                break
            await asyncio.sleep(0.1)

        assert self.bbot_server.scheduled_tasks.cron_task_ran, "cron_task did not run"
        assert self.bbot_server.scheduled_tasks.cron_task_2_ran, "cron_task_2 did not run"
        assert self.bbot_server.scheduled_tasks.cron_task_3_ran, "cron_task_3 did not run"
