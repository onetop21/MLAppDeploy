import json
from typing import Any, Generator, Dict

from fastapi.responses import StreamingResponse


def jsonify_response(generator):
    for elem in generator:
        yield json.dump(elem)


class DictStreamingResponse(StreamingResponse):

    def __init__(self, content: Generator[Dict[str, str], None, None], *args, **kwargs):
        super().__init__(jsonify_response(content), *args, **kwargs)
