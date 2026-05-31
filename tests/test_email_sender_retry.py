"""Tests for SMTP retry behaviour in send_email().

Connection-level failures (TCP timeouts, server disconnects) must be retried;
auth/recipient errors must NOT be retried because they will not self-resolve.
"""

import smtplib
import socket
from unittest.mock import MagicMock, patch

import pytest

from be_invest import email_sender


def _make_sender_env(monkeypatch):
    monkeypatch.setattr(email_sender, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(email_sender, "SMTP_PASSWORD", "pw")
    monkeypatch.setattr(email_sender, "SMTP_FROM_EMAIL", "user@example.com")


def test_retries_transient_connect_error_then_succeeds(monkeypatch):
    _make_sender_env(monkeypatch)
    monkeypatch.setattr(email_sender.time, "sleep", lambda *_a, **_k: None)

    successful_server = MagicMock()
    successful_server.__enter__.return_value = successful_server
    successful_server.__exit__.return_value = False

    side_effects = [
        smtplib.SMTPConnectError(421, b"transient timeout"),
        socket.timeout("timed out"),
        successful_server,
    ]

    with patch.object(email_sender.smtplib, "SMTP", side_effect=side_effects) as mock_smtp:
        email_sender.send_email("subj", "<p>body</p>", ["to@example.com"])

    assert mock_smtp.call_count == 3
    successful_server.login.assert_called_once_with("user@example.com", "pw")
    successful_server.sendmail.assert_called_once()


def test_does_not_retry_auth_error(monkeypatch):
    _make_sender_env(monkeypatch)
    monkeypatch.setattr(email_sender.time, "sleep", lambda *_a, **_k: None)

    bad_server = MagicMock()
    bad_server.__enter__.return_value = bad_server
    bad_server.__exit__.return_value = False
    bad_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad creds")

    with patch.object(email_sender.smtplib, "SMTP", return_value=bad_server) as mock_smtp:
        with pytest.raises(smtplib.SMTPAuthenticationError):
            email_sender.send_email("subj", "<p>body</p>", ["to@example.com"])

    assert mock_smtp.call_count == 1


def test_gives_up_after_max_attempts(monkeypatch):
    _make_sender_env(monkeypatch)
    monkeypatch.setattr(email_sender.time, "sleep", lambda *_a, **_k: None)

    with patch.object(
        email_sender.smtplib,
        "SMTP",
        side_effect=smtplib.SMTPConnectError(421, b"network down"),
    ) as mock_smtp:
        with pytest.raises(smtplib.SMTPConnectError):
            email_sender.send_email("subj", "<p>body</p>", ["to@example.com"])

    assert mock_smtp.call_count == email_sender._SMTP_MAX_ATTEMPTS
