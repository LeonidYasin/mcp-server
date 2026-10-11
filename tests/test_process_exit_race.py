"""#79: deterministic /proc exit races; no real PID signals or weakened guards."""
import errno
from unittest.mock import MagicMock

import pytest
from mcp_server.tools.process import process_ops as po


@pytest.mark.parametrize('error',[FileNotFoundError(errno.ENOENT,'gone'),
                                   ProcessLookupError(errno.ESRCH,'gone')])
@pytest.mark.parametrize('stage',['open','iterate'])
def test_proc_disappearance_during_open_or_iteration_is_gone(monkeypatch,error,stage):
    handle=MagicMock()
    handle.__enter__.return_value=handle
    handle.__iter__.side_effect=error
    opening=MagicMock(side_effect=error) if stage=='open' else MagicMock(return_value=handle)
    monkeypatch.setattr('builtins.open',opening)
    assert po._proc_state(4242) is None
    if stage=='iterate':handle.__exit__.assert_called_once()


@pytest.mark.parametrize('error',[PermissionError(errno.EACCES,'denied'),OSError(errno.EIO,'io failure')])
@pytest.mark.parametrize('stage',['open','iterate'])
def test_unrelated_os_errors_not_converted_to_dead(monkeypatch,error,stage):
    handle=MagicMock();handle.__enter__.return_value=handle;handle.__iter__.side_effect=error
    monkeypatch.setattr('builtins.open',MagicMock(side_effect=error) if stage=='open' else MagicMock(return_value=handle))
    with pytest.raises(type(error)):po._proc_state(4242)


@pytest.mark.parametrize('observed,alive',[(None,False),('Z',False),('R',True),('S',True)])
def test_one_saved_post_reap_read_not_two_inconsistent_reads(monkeypatch,observed,alive):
    # Old code could combine Z-not-None with a third None-not-Z and report True.
    states=MagicMock(side_effect=['Z',observed,None])
    reap=MagicMock()
    monkeypatch.setattr(po,'_proc_state',states)
    monkeypatch.setattr(po,'_reap_if_zombie',reap)
    assert po._is_alive(4242) is alive
    assert states.call_count==2
    reap.assert_called_once_with(4242)


def test_is_alive_returns_false_when_proc_disappears_during_iteration(monkeypatch):
    handle=MagicMock();handle.__enter__.return_value=handle
    handle.__iter__.side_effect=ProcessLookupError(errno.ESRCH,'gone')
    monkeypatch.setattr('builtins.open',MagicMock(return_value=handle))
    assert po._is_alive(4242) is False
