"""Compatibility exports; no duplicate implementation or old job-log transport."""
from mcp_server.tools.github.build_logs import get_android_build_error, get_ios_build_error
__all__=["get_android_build_error","get_ios_build_error"]
