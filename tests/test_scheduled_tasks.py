# import asyncio
# from contextlib import suppress


# TODO:
# - how many tasks can be executing at a time?
# - is it configurable?
# - what if a task runs into overtime and a bunch of the same one get queued?
# - can we reject duplicates?
# - dependencies (DAG / airflow?)


# async def test_scheduled_tasks(mongo_cleanup):
#     from bbot_server import BBOTServer
#     from bbot_server.watchdog import BBOTWatchdog
#     from bbot_server.applets.base import BaseApplet, watchdog_task

#     class ScheduledTaskApplet(BaseApplet):
#         name = "Scheduled Tasks"

#         def __init__(self, *args, **kwargs):
#             super().__init__(*args, **kwargs)
#             self.cron_task_ran = False
#             self.cron_task_2_ran = False
#             self.cron_task_3_ran = False

#         @watchdog_task(cron="* * * * *")
#         async def cron_task(self):
#             self.cron_task_ran = True

#         @watchdog_task(cron="* * * * *", cron_config_key="test.cron_task_2")
#         async def cron_task_2(self):
#             self.cron_task_2_ran = True

#         @watchdog_task(cron="* * * * *", cron_config_key="test.cron_task_3")
#         async def cron_task_3(self):
#             self.cron_task_3_ran = True

#     config = {"test": {"cron_task_2": "*/1 * * * *"}}

#     bbot_server = BBOTServer(config=config)
#     await bbot_server.setup()
#     watchdog = BBOTWatchdog(bbot_server)
#     await watchdog.start()

#     try:
#         app = bbot_server.include_app(ScheduledTaskApplet)
#         # register tasks on the bbot server side
#         await app._setup()
#         # register tasks on the watchdog side
#         await app.register_watchdog_tasks(watchdog.broker)

#         assert bbot_server.scheduled_tasks.cron_task_ran is False, "cron_task ran before setup"
#         assert bbot_server.scheduled_tasks.cron_task_2_ran is False, "cron_task_2 ran before setup"
#         assert bbot_server.scheduled_tasks.cron_task_3_ran is False, "cron_task_3 ran before setup"

#         all_tasks = watchdog.broker.get_all_tasks()

#         assert "tests.test_scheduled_tasks:cron_task" in all_tasks, "cron_task is not registered"
#         assert "tests.test_scheduled_tasks:cron_task_2" in all_tasks, "cron_task_2 is not registered"
#         assert "tests.test_scheduled_tasks:cron_task_3" in all_tasks, "cron_task_3 is not registered"

#         assert all_tasks["tests.test_scheduled_tasks:cron_task"].labels == {"schedule": [{"cron": "* * * * *"}]}
#         assert all_tasks["tests.test_scheduled_tasks:cron_task_2"].labels == {"schedule": [{"cron": "*/1 * * * *"}]}
#         assert all_tasks["tests.test_scheduled_tasks:cron_task_3"].labels == {"schedule": [{"cron": "* * * * *"}]}

#         # wait for cron tasks to run
#         for i in range(60 * 10):
#             if all(
#                 [
#                     bbot_server.scheduled_tasks.cron_task_ran,
#                     bbot_server.scheduled_tasks.cron_task_2_ran,
#                     bbot_server.scheduled_tasks.cron_task_3_ran,
#                 ]
#             ):
#                 break
#             await asyncio.sleep(0.1)

#         assert bbot_server.scheduled_tasks.cron_task_ran, "cron_task did not run"
#         assert bbot_server.scheduled_tasks.cron_task_2_ran, "cron_task_2 did not run"
#         assert bbot_server.scheduled_tasks.cron_task_3_ran, "cron_task_3 did not run"

#     finally:
#         with suppress(Exception):
#             await bbot_server.stop()
#         with suppress(Exception):
#             await watchdog.stop()
