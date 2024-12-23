class BaseAssetModule:
    def absorb_event(self, asset, event):
        raise NotImplementedError()

    def archive_event(self, asset, event):
        raise NotImplementedError()

    @property
    def name(self):
        return self.__class__.__name__
