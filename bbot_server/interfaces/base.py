import logging


class BaseInterface:
    """
    Interface is the frontend of the BBOT IO API.

    User --> Interface --> Applets --> Backend

    It's a thin layer between the user and the applet

    By default it's a no-op

    But can be used to implement RPC-like functionality, like a web client
    """

    interface_type = None

    def __init__(self, **kwargs):
        self.log = logging.getLogger(f"bbot_server.interfaces.{self.__class__.__name__.lower()}")

        from bbot_server.applets import BBOTServerRootApplet

        self.applet = BBOTServerRootApplet(**kwargs)
        self.applet._interface = self
        self.applet._interface_type = self.interface_type

    def __getattr__(self, name):
        """
        Default is to pass through to the applet
        """
        applet = self.__getattribute__("applet")
        return getattr(applet, name)
