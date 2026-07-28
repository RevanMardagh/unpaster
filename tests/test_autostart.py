import winreg

import pytest

from unpaster import autostart

TEST_KEY = r"Software\unpaster-tests\Run"


@pytest.fixture(autouse=True)
def clean_key():
    yield
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, TEST_KEY)
    except FileNotFoundError:
        pass


def test_disabled_when_key_does_not_exist():
    assert autostart.is_enabled(key_path=TEST_KEY) is False


def test_enable_then_is_enabled():
    autostart.enable(r"C:\apps\unpaster.exe", key_path=TEST_KEY)
    assert autostart.is_enabled(key_path=TEST_KEY) is True


def test_enable_writes_a_quoted_path():
    autostart.enable(r"C:\Program Files\unpaster\unpaster.exe", key_path=TEST_KEY)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, TEST_KEY) as key:
        value, kind = winreg.QueryValueEx(key, autostart.VALUE_NAME)
    assert value == r'"C:\Program Files\unpaster\unpaster.exe"'
    assert kind == winreg.REG_SZ


def test_enable_is_idempotent():
    autostart.enable(r"C:\apps\unpaster.exe", key_path=TEST_KEY)
    autostart.enable(r"C:\apps\unpaster.exe", key_path=TEST_KEY)
    assert autostart.is_enabled(key_path=TEST_KEY) is True


def test_enable_overwrites_an_old_path():
    autostart.enable(r"C:\old\unpaster.exe", key_path=TEST_KEY)
    autostart.enable(r"C:\new\unpaster.exe", key_path=TEST_KEY)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, TEST_KEY) as key:
        value, _ = winreg.QueryValueEx(key, autostart.VALUE_NAME)
    assert value == r'"C:\new\unpaster.exe"'


def test_disable_removes_the_value():
    autostart.enable(r"C:\apps\unpaster.exe", key_path=TEST_KEY)
    autostart.disable(key_path=TEST_KEY)
    assert autostart.is_enabled(key_path=TEST_KEY) is False


def test_disable_when_absent_is_harmless():
    autostart.disable(key_path=TEST_KEY)
    assert autostart.is_enabled(key_path=TEST_KEY) is False


def test_current_command_is_quoted_and_non_empty():
    command = autostart.current_command()
    assert command.startswith('"')
    assert command.count('"') >= 2
