import keyring
import pytest

from orion.config import Config


def test_switching_persisted_key_to_session_removes_key_after_restart(tmp_path):
    config = Config(tmp_path)
    config.set_api_key('tmdb', 'persisted-key')

    result = config.set_api_key('tmdb', ' session-key ', session_only=True)

    assert result == {'configured': True, 'storage': 'session'}
    assert config.get_api_key('tmdb') == 'session-key'
    assert Config(tmp_path).get_api_key('tmdb') == ''


def test_session_switch_discovers_and_removes_uncached_persisted_key(tmp_path):
    Config(tmp_path).set_api_key('tmdb', 'persisted-key')
    config = Config(tmp_path)

    config.set_api_key('tmdb', 'session-key', session_only=True)

    assert config.get_api_key('tmdb') == 'session-key'
    assert Config(tmp_path).get_api_key('tmdb') == ''


@pytest.mark.parametrize('cached', [False, True])
@pytest.mark.parametrize('error', [RuntimeError, keyring.errors.PasswordDeleteError, keyring.errors.NoKeyringError])
def test_failed_persisted_key_removal_preserves_active_key(tmp_path, monkeypatch, cached, error):
    Config(tmp_path).set_api_key('tmdb', 'persisted-key')
    config = Config(tmp_path)
    if cached:
        assert config.get_api_key('tmdb') == 'persisted-key'

    def unavailable(*args):
        raise error('credential removal failed')

    monkeypatch.setattr(keyring, 'delete_password', unavailable)
    with pytest.raises(ValueError):
        config.set_api_key('tmdb', 'replacement-key', session_only=True)

    assert config.get_api_key('tmdb') == 'persisted-key'
    assert Config(tmp_path).get_api_key('tmdb') == 'persisted-key'
    assert 'tmdb' not in config._session_services


def test_repeated_session_edits_and_clear_work_without_vault(tmp_path, monkeypatch):
    config = Config(tmp_path)
    config.set_api_key('tmdb', 'first-key', session_only=True)

    def unavailable(*args):
        raise keyring.errors.NoKeyringError('No OS credential vault')

    monkeypatch.setattr(keyring, 'get_password', unavailable)
    monkeypatch.setattr(keyring, 'delete_password', unavailable)
    assert config.set_api_key('tmdb', 'second-key', session_only=True) == {'configured': True, 'storage': 'session'}
    assert config.get_api_key('tmdb') == 'second-key'
    assert config.set_api_key('tmdb', '', session_only=True) == {'configured': False, 'storage': 'session'}
    assert config.get_api_key('tmdb') == ''


def test_fresh_session_key_works_without_os_vault(tmp_path, monkeypatch):
    def unavailable(*args):
        raise keyring.errors.NoKeyringError('No OS credential vault')

    monkeypatch.setattr(keyring, 'get_password', unavailable)
    monkeypatch.setattr(keyring, 'delete_password', unavailable)
    config = Config(tmp_path)
    assert config.get_api_key('tmdb') == ''
    assert config.set_api_key('tmdb', 'session-key', session_only=True) == {'configured': True, 'storage': 'session'}
    assert config.get_api_key('tmdb') == 'session-key'


def test_known_persisted_key_cannot_switch_when_vault_becomes_unavailable(tmp_path, monkeypatch):
    config = Config(tmp_path)
    config.set_api_key('tmdb', 'persisted-key')

    def unavailable(*args):
        raise keyring.errors.NoKeyringError('No OS credential vault')

    monkeypatch.setattr(keyring, 'get_password', unavailable)
    monkeypatch.setattr(keyring, 'delete_password', unavailable)
    with pytest.raises(ValueError):
        config.set_api_key('tmdb', 'session-key', session_only=True)
    assert config.get_api_key('tmdb') == 'persisted-key'


def test_failed_vault_read_is_not_mistaken_for_absent_persisted_key(tmp_path, monkeypatch):
    Config(tmp_path).set_api_key('tmdb', 'persisted-key')
    config = Config(tmp_path)
    original_get = keyring.get_password

    def unavailable(*args):
        raise RuntimeError('credential vault temporarily locked')

    monkeypatch.setattr(keyring, 'get_password', unavailable)
    assert config.get_api_key('tmdb') == ''
    with pytest.raises(ValueError):
        config.set_api_key('tmdb', 'session-key', session_only=True)

    monkeypatch.setattr(keyring, 'get_password', original_get)
    assert Config(tmp_path).get_api_key('tmdb') == 'persisted-key'
