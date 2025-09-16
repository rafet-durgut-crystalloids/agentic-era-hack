import subprocess
import shlex
from typing import Union, List, Tuple, Optional, Dict


def run_cli(
    cmd: Union[str, List[str]],
    check: bool = True,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None
) -> Tuple[int, str, str]:
    """
    Execute a shell command.

    Args:
        cmd: Command to run. Can be a single string (will be shell-split) or a list of arguments.
        check: If True, raises CalledProcessError on non-zero exit.
        cwd: Optional working directory in which to run the command.
        env: Optional dict of environment variables to override.

    Returns:
        A tuple (return_code, stdout, stderr).
    """
    if isinstance(cmd, str):
        args = shlex.split(cmd)
    else:
        args = cmd

    result = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=env,
    )

    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            returncode=result.returncode,
            cmd=cmd,
            output=result.stdout,
            stderr=result.stderr,
        )

    return result.returncode, result.stdout, result.stderr


def run_gcloud(
    gcloud_args: Union[str, List[str]],
    check: bool = True,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None
) -> Tuple[int, str, str]:
    """
    Execute a `gcloud` CLI command.

    Args:
        gcloud_args: Arguments to pass to `gcloud` (string or list).
        check: If True, raises CalledProcessError on non-zero exit.
        cwd: Optional working directory.
        env: Optional environment variables dict.

    Returns:
        A tuple (return_code, stdout, stderr).
    """
    if isinstance(gcloud_args, str):
        args = shlex.split(gcloud_args)
    else:
        args = gcloud_args

    # Prepend the `gcloud` executable
    return run_cli(["gcloud"] + args, check=check, cwd=cwd, env=env)