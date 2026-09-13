"""Same-directory atomic JSON replacement; retain the old file on write failure."""
import json
import os
import tempfile


def write_json(path, payload):
    path = os.path.abspath(path)
    fd, temporary = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.',
                                     suffix='.tmp', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
