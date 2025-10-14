class BBOTServerError(Exception):
    http_status_code = 500
    default_message = "An error occurred"

    def __init__(self, *args, detail=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.detail = detail or {}


class BBOTServerUnauthorizedError(BBOTServerError):
    http_status_code = 401
    default_message = "Unauthorized"


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


def handle_bbot_server_error(request, exc: Exception):
    """
    Catch BBOTServerErrors and transform them into appropriate FastAPI responses
    """
    from fastapi.responses import ORJSONResponse

    status_code = exc.http_status_code
    error_message = str(exc)
    message = error_message if error_message else exc.default_message
    return ORJSONResponse(
        status_code=status_code,
        content={"error": message, "detail": getattr(exc, "detail", {})},
    )
