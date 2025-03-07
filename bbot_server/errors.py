class BBOTServerError(Exception):
    pass


class BBOTServerForbiddenError(BBOTServerError):
    pass


class BBOTServerValueError(BBOTServerError):
    pass


class BBOTServerNotFoundError(BBOTServerError):
    pass
