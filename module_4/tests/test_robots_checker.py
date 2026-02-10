"""Tests for RobotsChecker — robots.txt compliance checker."""

import pytest
from unittest.mock import patch, MagicMock

import RobotsChecker as rc_module
from RobotsChecker import RobotsChecker


@pytest.mark.web
def test_init_sets_attributes(monkeypatch):
    monkeypatch.setattr(
        "urllib.robotparser.RobotFileParser.read", lambda self: None
    )
    monkeypatch.setattr(
        "urllib.robotparser.RobotFileParser.crawl_delay",
        lambda self, ua: 2.0,
    )
    checker = RobotsChecker("https://example.com/", "TestBot")
    assert checker.base_url == "https://example.com/"
    assert checker.user_agent == "TestBot"
    assert checker.crawl_delay == 2.0


@pytest.mark.web
def test_init_read_exception_warns(monkeypatch, capsys):
    def _raise(self):
        raise Exception("connection refused")

    monkeypatch.setattr("urllib.robotparser.RobotFileParser.read", _raise)
    checker = RobotsChecker("https://example.com/")
    assert checker.crawl_delay is None
    assert "Could not fetch robots.txt" in capsys.readouterr().err


@pytest.mark.web
def test_can_fetch_delegates(monkeypatch):
    monkeypatch.setattr(
        "urllib.robotparser.RobotFileParser.read", lambda self: None
    )
    monkeypatch.setattr(
        "urllib.robotparser.RobotFileParser.crawl_delay",
        lambda self, ua: None,
    )
    checker = RobotsChecker("https://example.com/")
    monkeypatch.setattr(checker.parser, "can_fetch", lambda ua, url: True)
    assert checker.can_fetch("https://example.com/page") is True

    monkeypatch.setattr(checker.parser, "can_fetch", lambda ua, url: False)
    assert checker.can_fetch("https://example.com/page") is False


@pytest.mark.web
def test_get_crawl_delay_returns_value(monkeypatch):
    monkeypatch.setattr(
        "urllib.robotparser.RobotFileParser.read", lambda self: None
    )
    monkeypatch.setattr(
        "urllib.robotparser.RobotFileParser.crawl_delay",
        lambda self, ua: 3.0,
    )
    checker = RobotsChecker("https://example.com/")
    assert checker.get_crawl_delay(0.5) == 3.0


@pytest.mark.web
def test_get_crawl_delay_returns_default(monkeypatch):
    monkeypatch.setattr(
        "urllib.robotparser.RobotFileParser.read", lambda self: None
    )
    monkeypatch.setattr(
        "urllib.robotparser.RobotFileParser.crawl_delay",
        lambda self, ua: None,
    )
    checker = RobotsChecker("https://example.com/")
    assert checker.get_crawl_delay(0.5) == 0.5