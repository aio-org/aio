from aiohttp import ClientWebSocketResponse as ClientWebSocketResponse
from typing import Any, Dict, Optional, Union

class Base(Exception): ...

def deprecated(version: str): ...

class HTTPException(Base):
    response: Any
    status: Any
    code: Any
    text: Any
    def __init__(self, response: _ResponseType, message: Optional[Union[str, Dict[str, Any]]]) -> None: ...

class ClientException(Base): ...
class LoginFailure(ClientException): ...
class Forbidden(HTTPException): ...

class NotFound(HTTPException):
    request: Any
    def __init__(self, request) -> None: ...

class Unauthorized(HTTPException):
    request: Any
    def __init__(self, request) -> None: ...

class RateLimitError(HTTPException): ...
class ServerError(HTTPException): ...
class TokenNotFound(HTTPException): ...
