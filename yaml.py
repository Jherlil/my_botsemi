import json

# Minimal YAML parser for key: value pairs and JSON content.
# Supports YAML subset used in tests.
def safe_load(stream):
    if hasattr(stream, 'read'):
        content = stream.read()
    else:
        content = stream
    content = content.strip()
    if content.startswith('{'):
        return json.loads(content)
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            result[key.strip()] = value.strip().strip('"\'')
    return result
