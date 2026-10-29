from unittest.mock import Mock

from Demo.tests.test_api import api, wait_done, parse_events


def test_replay_uses_original_events_without_services_and_recovers_cursor(api):
    client, app = api
    run_id = client.post('/api/runs', json={'question': 'Synthetic recording fixture'}).json()['run_id']
    original = wait_done(client, run_id)
    trace = parse_events(client.get(f'/api/runs/{run_id}/events').text)
    app.state.database.status = Mock(side_effect=AssertionError('Qdrant must not be called'))
    app.state.health.check = Mock(side_effect=AssertionError('Model readiness must not be called'))
    app.state.manager.start_reserved = Mock(side_effect=AssertionError('Inference must not be called'))
    replay = client.post('/api/replays', json={'run_id': run_id})
    assert replay.status_code == 201
    assert replay.json()['mode'] == 'replay'
    events_url = replay.json()['events_url']
    assert parse_events(client.get(events_url + '?speed=8').text) == trace
    assert parse_events(client.get(events_url + '?speed=8&after=3').text) == trace[3:]
    assert client.get(events_url + '?speed=0').status_code == 422
    assert client.get(events_url + '?after=9999').status_code == 422
    assert client.get(f'/api/runs/{run_id}').json() == original
    assert client.post('/api/replays', json={'run_id': 'expired'}).status_code == 404
