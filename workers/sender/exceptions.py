from fastapi import HTTPException


class NoTokenException(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="No token provided")


class InvalidTokenException(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Invalid token")


class UnauthorizedException(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Unauthorized")


class ServerError(Exception):
    def __init__(self):
        message = "An unexpected error occured in rpc_client.call()"
        super().__init__(message)
