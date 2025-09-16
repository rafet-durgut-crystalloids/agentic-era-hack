import os
import logging
import pathlib

log = logging.getLogger(__name__)

def load_env_vars(file_path: str) -> int:
    p = pathlib.Path(file_path)
    if not p.exists():
        log.warning("[env] File not found: %s (skipping)", file_path)
        return 0

    count = 0
    with p.open("r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if value.startswith(("'", '"')) and value.endswith(("'", '"')):
                value = value[1:-1]
            os.environ[key] = value
            count += 1

    log.info("✅ Loaded %d env vars from %s", count, file_path)
    return count