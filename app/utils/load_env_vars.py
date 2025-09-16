import os

def load_env_vars(file_path: str):
    """Load key=value pairs from a file and set as environment variables."""
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if value.startswith(("'", '"')) and value.endswith(("'", '"')):
                value = value[1:-1]
            os.environ[key] = value

    print(f"Loaded environment variables from {file_path}")