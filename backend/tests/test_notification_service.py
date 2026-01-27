import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import notification_service

def test_send_sms_notification_success(caplog):
    # Test logging behavior
    with caplog.at_level("INFO"):
        res = notification_service.send_sms_notification("1234567890", "Hello Test")
        assert res is True
        assert "SMS NOTIFICATION" in caplog.text
        assert "To: 1234567890" in caplog.text
        assert "Hello Test" in caplog.text

def test_send_sms_notification_no_phone():
    res = notification_service.send_sms_notification("", "No phone")
    assert res is False

@patch('notification_service.send_sms_notification')
def test_notify_team_assignment(mock_send):
    team_members = [
        {'profile': {'full_name': 'Alice', 'phone': '111'}},
        {'profile': {'full_name': 'Bob', 'phone': '222'}}
    ]
    notification_service.notify_team_assignment(team_members, "Broken Pipe", "Village X")
    
    assert mock_send.call_count == 2
    mock_send.assert_any_call('111', "Hello Alice, you have been assigned to: 'Broken Pipe' in Village X. Local coordinators will contact you soon.")
    mock_send.assert_any_call('222', "Hello Bob, you have been assigned to: 'Broken Pipe' in Village X. Local coordinators will contact you soon.")

@patch('notification_service.send_sms_notification')
def test_notify_problem_resolved(mock_send):
    notification_service.notify_problem_resolved("333", "Broken Pipe")
    mock_send.assert_called_with("333", "Good news! Your reported issue 'Broken Pipe' has been marked as resolved by our volunteers. Thank you for your patience.")
