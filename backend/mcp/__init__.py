"""Namespace bridge: merge pip ``mcp`` package into this local mcp package.

The backend/mcp/ directory defines local MCP server modules (account_mcp,
transactions_mcp, payments_mcp).  The pip-installed ``mcp`` package (required
by fastmcp) uses the same top-level name.  This shim extends this package's
``__path__`` so that submodules from both packages are importable under
``mcp`` (e.g. ``mcp.types`` from pip **and** ``mcp.account_mcp`` from here),
and re-executes the pip package's ``__init__.py`` so that its public exports
(``LoggingLevel``, ``ServerSession``, etc.) are also available via
``from mcp import …``.
"""

import os
import sys

_this_dir = os.path.dirname(os.path.abspath(__file__))

# Scan sys.path for the pip-installed mcp package directory and prepend it
# to __path__ so that pip submodules (mcp.types, mcp.server, …) are found.
for _search_dir in sys.path:
    # Only consider directories inside a site-packages tree – this avoids
    # picking up an unrelated local directory and limits the exec() below
    # to code already installed via pip.
    if "site-packages" not in _search_dir:
        continue
    _candidate = os.path.join(_search_dir, "mcp")
    if (
        os.path.isdir(_candidate)
        and os.path.realpath(_candidate) != os.path.realpath(_this_dir)
        and _candidate not in __path__
    ):
        __path__.insert(0, _candidate)
        # Execute the pip mcp package's __init__.py in our namespace so
        # that its public re-exports are available via ``from mcp import …``.
        _pip_init = os.path.join(_candidate, "__init__.py")
        if os.path.isfile(_pip_init):
            with open(_pip_init) as _f:
                exec(compile(_f.read(), _pip_init, "exec"))  # noqa: S102
        break
