import os

def get_env_var(var_name):
    """
    Retrieve a required environment variable.

    Args:
      var_name: Name of the environment variable.

    Returns:
      The value as a string.

    Raises:
      ValueError: If the variable is missing.
    """
    try:
        val = os.environ[var_name]
        return val
    except KeyError:
        raise ValueError(f"Missing environment variable: {var_name}")