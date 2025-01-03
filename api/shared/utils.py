import os
import logging
import typing

class EndpointFilter(logging.Filter):
    def __init__(
        self,
        path: str,
        *args: typing.Any,
        **kwargs: typing.Any,
    ):
        super().__init__(*args, **kwargs)
        self._path = path

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find(self._path) == -1