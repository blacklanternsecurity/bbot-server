from bbot_io.backends import BBOTBackend
from bbot_io.applets.base import BaseApplet


class BBOTIO(BaseApplet):

    def __init__(self, backend="sqlite", *args, **kwargs):
        # instantiate our IO module in the root app
        self.backend = BBOTBackend(backend, *args, **kwargs)
        super().__init__(self.backend)
        self.include_app("Events")
        self.include_app("Scans")
        self.include_app("Utils")
        self.include_app("Targets")
        # self.include_app("UserStates")
