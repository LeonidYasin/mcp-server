"""Opt-in rooms on the existing MCP endpoint; no IO during discovery."""
import os
if os.environ.get('ENABLE_AGENT_ROOMS', '').strip().lower() in {'1', 'true', 'yes', 'on'}:
    from .ops import (rooms_create, rooms_list, rooms_join, rooms_leave,
                      rooms_read, rooms_send, rooms_delete_message, rooms_close)
    __all__ = ['rooms_create', 'rooms_list', 'rooms_join', 'rooms_leave',
               'rooms_read', 'rooms_send', 'rooms_delete_message', 'rooms_close']
else:
    __all__ = []
