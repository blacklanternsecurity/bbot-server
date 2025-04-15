class BBOTServerError(Exception):
    http_status_code = 500
    default_message = "An error occurred"

    def __init__(self, *args, detail=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.detail = detail or {}


class BBOTServerForbiddenError(BBOTServerError):
    http_status_code = 403
    default_message = "Forbidden"


class BBOTServerValueError(BBOTServerError):
    http_status_code = 400
    default_message = "Invalid value"


class BBOTServerNotFoundError(BBOTServerError):
    http_status_code = 404
    default_message = "Not found"


# Automatically build mapping of status codes to error classes
HTTP_STATUS_MAPPINGS = {}


# Recursively register all BBOTServerError subclasses in the STATUS_CODE_TO_ERROR_CLASS dictionary.
def gather_status_codes(cls):
    HTTP_STATUS_MAPPINGS[cls.http_status_code] = cls
    for subclass in cls.__subclasses__():
        gather_status_codes(subclass)


# Start with the base error class
gather_status_codes(BBOTServerError)
