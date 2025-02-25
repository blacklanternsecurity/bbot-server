class BBOTServerError(Exception):
    pass


class BBOTValueError(BBOTServerError):
    pass


class BBOTNotFoundError(BBOTServerError):
    pass
