"""
notebooklm/__init__.py — transparent redirect to the installed notebooklm-py.

This local 'notebooklm/' directory shadows the pip-installed 'notebooklm-py'
package. This file resolves the conflict by:
  1. Pointing __path__ to the installed package directory so all submodule
     imports (notebooklm.client, notebooklm.types, etc.) resolve from
     site-packages.
  2. exec()'ing the installed __init__.py in this namespace so every symbol
     (__version__, NotebookLMClient, exceptions, types, …) is available here,
     exactly as if the local directory did not exist.
"""
import os
import sys

_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)

# Locate the installed notebooklm package, skipping our local directory.
_installed_dir: str | None = None
for _entry in sys.path:
    _abs = os.path.abspath(_entry) if _entry else os.path.abspath(".")
    if _abs == _project_root:
        continue
    _candidate = os.path.join(_abs, "notebooklm")
    if os.path.isdir(_candidate) and os.path.abspath(_candidate) != _this_dir:
        _installed_dir = _candidate
        break

if _installed_dir is None:
    raise ImportError(
        "notebooklm-py is not installed. "
        "Run: pip install 'notebooklm-py[browser]' && playwright install chromium && notebooklm login"
    )

# Redirect submodule lookups to the installed package directory.
__path__ = [_installed_dir]

# Execute the installed __init__.py in this namespace so that all public
# symbols (__version__, NotebookLMClient, exceptions, types, …) are
# available as if this local package did not exist.
_init_file = os.path.join(_installed_dir, "__init__.py")
with open(_init_file, encoding="utf-8") as _f:
    exec(compile(_f.read(), _init_file, "exec"), globals())  # noqa: S102
