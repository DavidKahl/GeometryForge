import json
import threading

import pytest

from geometryforge import blender_session
from geometryforge.houdini_transport import server


class FakeBridge:
    """Stands in for blender_bootstrap: same transport, scripted job states."""

    def __init__(self, states):
        self.states, self.calls, self.cancelled = list(states), [], False

    def methods(self):
        return {'hello': lambda: blender_session.VERSION, 'submit': self.submit, 'status': self.status, 'cancel': self.cancel}

    def submit(self, job, payload):
        self.calls.append(json.loads(payload))
        return job

    def status(self, job):
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return json.dumps(state)

    def cancel(self, job):
        self.cancelled = True


@pytest.fixture
def bridge(monkeypatch):
    def make(states):
        fake = FakeBridge(states)
        srv = server(0, 'secret', fake.methods())
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        record = {'port': srv.server_address[1], 'token': 'secret', 'pid': 0}
        monkeypatch.setattr(blender_session, 'start', lambda explicit=None: record)
        monkeypatch.setattr(blender_session, 'owned', lambda r: True)
        monkeypatch.setattr(blender_session.time, 'sleep', lambda s: None)
        return fake
    return make


def test_waits_through_reveal_and_returns_on_evidence(bridge):
    fake = bridge([{'status': 'running', 'build_seconds': 1}, {'status': 'running', 'build_seconds': 2, 'paused': True},
                   {'status': 'passed', 'build_seconds': 3, 'result': {'mode': 'live'}}])
    assert blender_session.request({'out': 'x'}, timeout=10) == {'mode': 'live'}
    assert fake.calls == [{'out': 'x'}]


def test_failure_carries_the_bridge_error(bridge):
    bridge([{'status': 'failed', 'build_seconds': 0, 'error': 'Geometry edited while paused'}])
    with pytest.raises(RuntimeError, match='edited while paused'):
        blender_session.request({}, timeout=10)


def test_timeout_counts_build_time_and_cancels_without_closing_the_window(bridge):
    fake = bridge([{'status': 'running', 'build_seconds': 0}, {'status': 'running', 'build_seconds': 11}])
    with pytest.raises(TimeoutError, match='build time'):
        blender_session.request({}, timeout=10)
    assert fake.cancelled


def test_wrong_token_is_rejected(bridge):
    fake = bridge([{'status': 'passed', 'build_seconds': 0}])
    record = blender_session.start()
    from geometryforge.houdini_transport import Client
    with pytest.raises(RuntimeError, match='Invalid session credential'):
        Client(record['port'], 'wrong').invoke('status', 'job')
