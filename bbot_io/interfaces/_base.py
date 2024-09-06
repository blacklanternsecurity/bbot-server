import logging


class BaseInterface:
    """
    Interface is the frontend of the BBOT IO API.

    User --> Interface --> Applets --> Backend

    It's a thin layer between the user and the applet

    By default it's a no-op

    But can be used to implement RPC-like functionality, like a web client
    """

    def __init__(self, backend, **kwargs):
        self.log = logging.getLogger(f"bbot.io.interfaces.{self.__class__.__name__.lower()}")

        from bbot_io.applets import BBOTApplet

        self.applet = BBOTApplet(backend, **kwargs)

    def __getattr__(self, attr):
        # by default we just pass everything through to the applet
        return getattr(self.applet, attr)
