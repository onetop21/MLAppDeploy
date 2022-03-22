import json
from typing import Any, Generator, Dict

from fastapi.responses import StreamingResponse


def jsonify_response(generator):
    try:
        for elem in generator:
            yield json.dumps(elem)
    except Exception as e:
        yield json.dumps({'error': True, 'stream': f'{e.__class__.__name__}: {e}'})
        return


class DictStreamingResponse(StreamingResponse):

    def __init__(self, content: Generator[Dict[str, str], None, None], *args, **kwargs):
        super().__init__(jsonify_response(content), *args, **kwargs)
