"""Root conftest for the backend test suite.

Resolves the naming conflict between ``backend/mcp/`` (local package) and the
``mcp`` PyPI package (required by fastmcp internally):

* The ``backend/`` directory is prepended to ``sys.path`` by pytest, which
  makes ``import mcp`` resolve to ``backend/mcp/`` rather than the pip
  ``mcp`` package.
* We fix this by pre-loading the pip ``mcp`` package into ``sys.modules``
  before any test module is imported, and then extending its ``__path__`` to
  also include ``backend/mcp/`` so that ``from mcp.account_mcp import ...``
  continues to work.
"""

import os
import sys

_backend_dir = os.path.dirname(__file__)

# Temporarily remove backend/ from sys.path so that `import mcp` resolves to
# the pip package rather than backend/mcp/.
_filtered_path = [p for p in sys.path if p not in (_backend_dir, "")]
_original_path = sys.path[:]
sys.path = _filtered_path

import mcp as _pip_mcp  # noqa: E402 – intentional late import

# Extend the pip mcp package's search path to include backend/mcp/ so that
# `from mcp.account_mcp import …` and similar imports still resolve correctly.
_local_mcp = os.path.join(_backend_dir, "mcp")
if _local_mcp not in _pip_mcp.__path__:
    _pip_mcp.__path__.append(_local_mcp)

# Register the (now extended) pip mcp as the authoritative 'mcp' module so
# that fastmcp's internal `import mcp.types` / `from mcp import …` calls work.
sys.modules["mcp"] = _pip_mcp

# Restore sys.path so that all other local packages (services, agents, …) are
# still importable as usual.
sys.path = _original_path
