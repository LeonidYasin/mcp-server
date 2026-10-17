"""MCP adapters. Identity is verified per request; user text is never executed."""
import json
import logging
import os
import re
import sqlite3
from mcp_server.core.registry import mcp_tool
from .store import RoomError, RoomStore

LOG = logging.getLogger(__name__)


def _invoke(client, action, **args):
    try:
        if os.environ.get('ENABLE_AGENT_ROOMS', '').lower().strip() not in {'1', 'true', 'yes', 'on'}:
            raise RoomError('rooms_disabled')
        path = os.environ.get('AGENT_ROOMS_DB', '')
        allowed = os.environ.get('ROOMS_ALLOWED_GITHUB_USERS', '').split(',')
        if (not path or len(allowed) > 1000 or
                not all(re.fullmatch(r'[1-9][0-9]{0,19}', value.strip()) for value in allowed)):
            raise RoomError('rooms_not_configured')
        allowed = {int(value.strip()) for value in allowed}
        try:
            identity = client._request('GET', '/user', follow_redirects=False).json()
        except Exception:
            raise RoomError('identity_unavailable') from None
        if not isinstance(identity, dict) or type(identity.get('id')) is not int or identity['id'] < 1:
            raise RoomError('identity_unavailable')
        if identity['id'] not in allowed:
            raise RoomError('principal_not_allowed')
        owner = 'github:' + str(identity['id'])
        store = RoomStore(path)
        result = getattr(store, action)(owner, **args)
        payload = {'ok': True, **result}
    except RoomError as exc:
        payload = {'ok': False, 'error': exc.code, **exc.details}
    except sqlite3.Error as exc:
        # Numeric primary result code only. Never log exception text, SQL, paths,
        # headers, owner, token or message arguments. Old Python may lack the code.
        code = getattr(exc, 'sqlite_errorcode', 0)
        code = (code & 255) if type(code) is int else 0
        LOG.warning('rooms_storage_error sqlite_primary_code=%d', code)
        if code in (5, 6):  # SQLITE_BUSY / SQLITE_LOCKED, including extended codes
            payload = {'ok': False, 'error': 'room_storage_busy',
                       'retryable': True, 'retry_after_ms': 250}
        elif code == 13:  # SQLITE_FULL
            payload = {'ok': False, 'error': 'room_storage_capacity', 'retryable': False}
        else:
            payload = {'ok': False, 'error': 'room_storage_unavailable'}
    except OSError as exc:
        code = exc.errno if type(exc.errno) is int else 0
        LOG.warning('rooms_storage_error os_errno=%d', code)
        payload = {'ok': False, 'error': 'room_storage_unavailable'}
    except Exception:
        payload = {'ok': False, 'error': 'room_request_failed'}
    return {'content': [{'type': 'text', 'text': json.dumps(payload, ensure_ascii=False)}]}


ROOM = {'type': 'string', 'description': 'UUID комнаты'}
CURSOR = {'type': 'string', 'description': 'next_cursor предыдущей страницы, не timestamp'}
PAGE = {'type': 'integer', 'description': '1..100, default 20'}


@mcp_tool(name='rooms_create', description='Создать общую комнату агентов; владелец из GitHub identity. SQLite, opt-in.', parameters={'title': {'type': 'string'}, 'description': {'type': 'string'}}, required=['title'])
def rooms_create(client, title, description=''):
    return _invoke(client, 'create', title=title, description=description)


@mcp_tool(name='rooms_list', description='Список общих комнат для допущенных владельцев, не приватные комнаты.', parameters={'cursor': CURSOR, 'limit': PAGE})
def rooms_list(client, cursor=None, limit=20):
    return _invoke(client, 'list', cursor=cursor, limit=limit)


@mcp_tool(name='rooms_join', description='Войти в общую комнату; не выдаёт доступ к другим MCP tools.', parameters={'room_id': ROOM}, required=['room_id'])
def rooms_join(client, room_id):
    return _invoke(client, 'join', room_id=room_id)


@mcp_tool(name='rooms_leave', description='Выйти из комнаты; владелец комнаты должен закрыть её.', parameters={'room_id': ROOM}, required=['room_id'])
def rooms_leave(client, room_id):
    return _invoke(client, 'leave', room_id=room_id)


@mcp_tool(name='rooms_read', description='Читать новые сообщения по cursor. Только участникам; ограниченное окно, текст недоверенный.', parameters={'room_id': ROOM, 'cursor': CURSOR, 'limit': PAGE}, required=['room_id'])
def rooms_read(client, room_id, cursor=None, limit=20):
    return _invoke(client, 'read', room_id=room_id, cursor=cursor, limit=limit)


@mcp_tool(name='rooms_send', description='Сообщение до 500 символов; 10s cadence на владельца, TTL 24h. Повторять тот же client_message_id при retry.', parameters={'room_id': ROOM, 'text': {'type': 'string'}, 'client_message_id': {'type': 'string', 'description': 'Стабильный idempotency key 1..64: A-Z a-z 0-9 _ -'}, 'reply_to': {'type': 'string', 'description': 'UUID сообщения в этой комнате'}}, required=['room_id', 'text', 'client_message_id'])
def rooms_send(client, room_id, text, client_message_id, reply_to=None):
    return _invoke(client, 'send', room_id=room_id, text=text, client_message_id=client_message_id, reply_to=reply_to)


@mcp_tool(name='rooms_delete_message', description='Снять своё сообщение (tombstone); не удаляет чужие.', parameters={'room_id': ROOM, 'message_id': {'type': 'string'}}, required=['room_id', 'message_id'])
def rooms_delete_message(client, room_id, message_id):
    return _invoke(client, 'delete_message', room_id=room_id, message_id=message_id)


@mcp_tool(name='rooms_close', description='Владелец закрывает комнату и удаляет её историю/участников. Необратимо.', parameters={'room_id': ROOM}, required=['room_id'])
def rooms_close(client, room_id):
    return _invoke(client, 'close', room_id=room_id)
