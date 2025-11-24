from datetime import datetime, timedelta

import pytz  # pip install pytz

from google_apis import create_service

TIMEZONE = 'Asia/Kolkata'
DEFAULT_CALENDAR_ID = 'primary'   # can be changed based on calendarList()



def construct_calendar_service(client_secret_file: str):
    """
    Construct a Google Calendar API service object.
    NOTE: service_name must be 'calendar', not 'primary'.
    """
    # api_name: just used for token filename in your create_service
    api_name = "calendar"
    service_name = "calendar"  # this is what googleapiclient.build() expects

    service = create_service(client_secret_file, api_name, service_name)
    return service

def get_current_date():
    tz = pytz.timezone(TIMEZONE)
    current_date = datetime.now(tz=tz)
    current_date = current_date.strftime('%Y/%m/%d/')
    return current_date


def list_calendars(service):
    """
    Return the list of calendars the authorized account has access to.
    Useful if you want a specific calendarId instead of just 'primary'.
    """
    results = service.calendarList().list().execute()
    items = results.get('items', [])
    # You can inspect 'summary' and 'id' from each item
    return items


def get_events_for_date(service, date_str: str, calendar_id: str = DEFAULT_CALENDAR_ID):
    """
    Get all events for a specific date from a given calendar.

    Args:
        service: Google Calendar API service object.
        date_str: 'YYYY-MM-DD' string.
        calendar_id: calendar ID (e.g. 'primary' or from calendarList()).

    Returns:
        List of event dicts.
    """
    tz = pytz.timezone(TIMEZONE)
    date = datetime.strptime(date_str, "%Y-%m-%d").date()

    start_dt = tz.localize(datetime.combine(date, datetime.min.time()))
    end_dt = start_dt + timedelta(days=1)

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.isoformat(),
        timeMax=end_dt.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    return events_result.get('items', [])

TIMEZONE = "Asia/Kolkata"   # or whatever you set earlier
DEFAULT_CALENDAR_ID = "primary"


def _events_to_appointments(events, tz, day_start, day_end):
    """
    Convert Google Calendar events into (start_dt, end_dt) tuples,
    all normalized to timezone `tz` (e.g. Asia/Kolkata).
    """
    appointments = []

    for event in events:
        start = event.get("start", {})
        end = event.get("end", {})

        # --- start ---
        if "dateTime" in start:
            start_dt = datetime.fromisoformat(start["dateTime"])
        else:
            # all-day → block full day
            start_dt = day_start

        if start_dt.tzinfo is None:
            # No tz info → assume tz
            start_dt = tz.localize(start_dt)
        else:
            # Has tz info (maybe UTC) → convert to tz
            start_dt = start_dt.astimezone(tz)

        # --- end ---
        if "dateTime" in end:
            end_dt = datetime.fromisoformat(end["dateTime"])
        else:
            end_dt = day_end

        if end_dt.tzinfo is None:
            end_dt = tz.localize(end_dt)
        else:
            end_dt = end_dt.astimezone(tz)

        # Clamp to working hours
        start_dt = max(start_dt, day_start)
        end_dt = min(end_dt, day_end)

        if start_dt < end_dt:
            appointments.append((start_dt, end_dt))

    return appointments

def get_slots(hours, appointments, duration=timedelta(hours=1)):
    free_slots = []
    slots = sorted([(hours[0], hours[0])] + appointments + [(hours[1], hours[1])])
    for start, end in ((slots[i][1], slots[i+1][0]) for i in range(len(slots)-1)):
        assert start <= end, "Cannot attend all appointments"
        while start + duration <= end:
            #print(start, start + duration)
            free_slots.append((start, start + duration))
            start += duration
    return free_slots

def next_day_hours(hours, begin = (9,0), finish = (17,0)):
    next_day = hours[0].date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, begin[0], begin[1])
    end = datetime(next_day.year, next_day.month, next_day.day, finish[0], finish[1])

    return start, end


def find_free_slots_for_date(
    service,
    date_str: str,
    calendar_id: str = DEFAULT_CALENDAR_ID,
    work_start: str = "09:00",
    work_end: str = "18:00",
    slot_minutes: int = 30,
    max_days_ahead: int = 1,
):
    """
    Compute free time slots starting from a given date, within doctor's working hours.
    Uses get_slots() and next_day_hours().

    Args:
        service: Google Calendar service.
        date_str: 'YYYY-MM-DD' (starting date to check).
        calendar_id: calendar id to inspect.
        work_start: working day start time in 'HH:MM' (24h).
        work_end: working day end time in 'HH:MM'.
        slot_minutes: minimum free slot size.
        max_days_ahead: how many days ahead to search if the given day is full.

    Returns:
        (date_str_for_slots, hours_tuple, free_slots_list)
        where free_slots_list is a list of (start_datetime, end_datetime) tuples.
        If nothing found within range, returns (None, None, []).
    """
    tz = pytz.timezone(TIMEZONE)

    base_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    start_hour, start_min = map(int, work_start.split(":"))
    end_hour, end_min = map(int, work_end.split(":"))
    duration = timedelta(minutes=slot_minutes)

    # Starting hours for the first day
    current_hours = (
        tz.localize(datetime.combine(base_date, datetime.min.time()).replace(hour=start_hour, minute=start_min)),
        tz.localize(datetime.combine(base_date, datetime.min.time()).replace(hour=end_hour, minute=end_min)),
    )

    for offset in range(max_days_ahead + 1):
        # Compute current date
        current_date = base_date + timedelta(days=offset)
        current_date_str = current_date.strftime("%Y-%m-%d")

        if offset > 0:
            # Move hours to next day while keeping same time range
            current_hours = next_day_hours(
                current_hours,
                begin=(start_hour, start_min),
                finish=(end_hour, end_min),
            )
            # Localize (next_day_hours returns naive)
            current_hours = (
                tz.localize(current_hours[0]),
                tz.localize(current_hours[1]),
            )

        day_start, day_end = current_hours

        # 1. Get events for that date from Google Calendar
        events = get_events_for_date(service, current_date_str, calendar_id)

        # 2. Convert events to appointments [(start, end), ...]
        appointments = _events_to_appointments(events, tz, day_start, day_end)

        # 3. Use your get_slots() to compute free slots
        free_slots = get_slots(
            hours=current_hours,
            appointments=appointments,
            duration=duration,
        )

        if free_slots:
            return current_date_str, current_hours, free_slots

    # No free slots found in range
    return None, None, []

def create_appointment_event(
    service,
    patient_name: str,
    date_str: str,
    time_str: str,
    description: str,
    calendar_id: str = DEFAULT_CALENDAR_ID,
    duration_minutes: int = 30,
):
    """
    Create an appointment event in the doctor’s calendar.

    Args:
        service: Google Calendar service.
        patient_name: name of patient.
        date_str: 'YYYY-MM-DD'
        time_str: 'HH:MM' (24h)
        description: details/symptoms.
        calendar_id: which calendar to insert into.
        duration_minutes: appointment length.

    Returns:
        The created event resource dict.
    """
    tz = pytz.timezone(TIMEZONE)
    start_dt = tz.localize(
        datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    )
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    event_body = {
        "summary": f"Appointment: {patient_name}",
        "description": description,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
    }

    created_event = service.events().insert(
        calendarId=calendar_id,
        body=event_body
    ).execute()

    return created_event
