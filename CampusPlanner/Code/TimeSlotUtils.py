"""Shared helpers for weekday slots and date-based event slots."""

from datetime import datetime, timedelta, timezone

from Constants import VALID_DAYS

LOCAL_TIME_ZONE = timezone(timedelta(hours=8))
MIN_TIMESTAMP = 86_400
MAX_TIMESTAMP = 4_102_444_800


def IsTimestampDay(day):
    return (
        isinstance(day, int)
        and not isinstance(day, bool)
        and MIN_TIMESTAMP <= day < MAX_TIMESTAMP
    )


def IsValidTimeSlotDay(day):
    return (
        isinstance(day, int)
        and not isinstance(day, bool)
        and (day in VALID_DAYS or IsTimestampDay(day))
    )


def GetWeekday(day):
    if IsTimestampDay(day):
        return datetime.fromtimestamp(day, LOCAL_TIME_ZONE).isoweekday()
    return day


def GetLocalDate(day):
    if IsTimestampDay(day):
        return datetime.fromtimestamp(day, LOCAL_TIME_ZONE).date()
    return None


def SameSlotDay(firstDay, secondDay):
    firstDate = GetLocalDate(firstDay)
    secondDate = GetLocalDate(secondDay)
    if firstDate is not None and secondDate is not None:
        return firstDate == secondDate
    return GetWeekday(firstDay) == GetWeekday(secondDay)


def TimeSlotsOverlap(firstSlots, secondSlots):
    return [
        firstSlot
        for firstSlot in firstSlots
        for secondSlot in secondSlots
        if firstSlot.get("period") == secondSlot.get("period")
        and SameSlotDay(firstSlot.get("day"), secondSlot.get("day"))
    ]


def GetDateLabel(day):
    eventDate = GetLocalDate(day)
    return eventDate.isoformat() if eventDate is not None else None
