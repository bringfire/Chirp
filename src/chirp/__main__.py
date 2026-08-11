"""Entry point: python -m chirp."""

from __future__ import annotations

import os
import socket
import sys
from typing import BinaryIO, Sequence

import uvicorn

from chirp.timeout_policy import load_canonical_environment
from chirp.vertex_bootstrap import (
    VertexBootstrapError,
    read_managed_bootstrap,
    start_retirement_listener,
)


def _run_server(server_module: object, *, rook_managed: bool) -> None:
    requested_port = int(os.environ.get("CHIRP_PORT", "0"))
    reload = os.environ.get("CHIRP_RELOAD", "0") == "1"
    if reload and rook_managed:
        raise VertexBootstrapError()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", requested_port))
    actual_port = sock.getsockname()[1]
    os.environ["_CHIRP_BOUND_PORT"] = str(actual_port)
    server_module.configure_bound_port(actual_port)

    if reload:
        sock.close()
        uvicorn.run(
            "chirp.server:app",
            host="127.0.0.1",
            port=actual_port,
            reload=True,
            timeout_graceful_shutdown=30,
        )
        return

    config = uvicorn.Config(
        server_module.app,
        host="127.0.0.1",
        timeout_graceful_shutdown=30,
    )
    server = uvicorn.Server(config)
    start_retirement_listener(server, rook_managed=rook_managed)
    server.run(sockets=[sock])


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: BinaryIO | None = None,
) -> None:
    load_canonical_environment()
    arguments = list(sys.argv[1:] if argv is None else argv)
    input_stream = sys.stdin.buffer if stdin is None else stdin
    rook_managed, bootstrap = read_managed_bootstrap(arguments, input_stream)

    # Import only after the private bootstrap has been accepted so no model is
    # initialized from an incomplete or malformed managed launch.
    from chirp import server as server_module

    server_module.configure_runtime(
        rook_managed=rook_managed,
        vertex_bootstrap=bootstrap,
    )
    _run_server(server_module, rook_managed=rook_managed)


if __name__ == "__main__":
    main()
