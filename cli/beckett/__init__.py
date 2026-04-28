from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("beckett")
except PackageNotFoundError:  # pragma: no cover - running from a bare source tree
    __version__ = "0.2.1"
