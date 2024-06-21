class BaseIO:
    def __init__(self, *args, **kwargs):
        self.setup(*args, **kwargs)

    def get_subdomains(self):
        raise NotImplementedError
