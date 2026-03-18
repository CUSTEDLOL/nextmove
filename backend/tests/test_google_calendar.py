import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from app.services.calendar_google import get_free_slots, FreeSlotResult


def make_event(hour_start, hour_end):
    base = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "start": {"dateTime": base.replace(hour=hour_start).isoformat() + "Z"},
        "end":   {"dateTime": base.replace(hour=hour_end).isoformat() + "Z"},
    }


def mock_service(events):
    svc = MagicMock()
    svc.events().list().execute.return_value = {"items": events}
    return svc


def test_no_events_returns_full_day():
    svc = mock_service([])
    day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    slots = get_free_slots(svc, "primary", day, study_start=9, study_end=17)
    assert len(slots) == 1
    assert slots[0].start.hour == 9
    assert slots[0].end.hour == 17


def test_event_splits_free_slots():
    svc = mock_service([make_event(10, 11)])
    day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    slots = get_free_slots(svc, "primary", day, study_start=9, study_end=17)
    assert len(slots) == 2
    assert slots[0].start.hour == 9
    assert slots[0].end.hour == 10
    assert slots[1].start.hour == 11
    assert slots[1].end.hour == 17


def test_event_at_start_leaves_one_slot():
    svc = mock_service([make_event(9, 11)])
    day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    slots = get_free_slots(svc, "primary", day, study_start=9, study_end=17)
    assert len(slots) == 1
    assert slots[0].start.hour == 11


def test_multiple_events():
    svc = mock_service([make_event(9, 10), make_event(12, 14)])
    day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    slots = get_free_slots(svc, "primary", day, study_start=9, study_end=17)
    assert len(slots) == 2  # 10-12 and 14-17
