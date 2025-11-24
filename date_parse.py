import re
from datetime import datetime, date, timedelta
import pytz
TIMEZONE = pytz.timezone('Asia/Kolkata')

def get_current_date():
    current_date = datetime.now(tz=TIMEZONE)
    current_date = current_date.strftime('%Y-%m-%d')
    year = current_date.split('-')[0]
    month = current_date.split('-')[1]
    day = current_date.split('-')[2]
    cur = date(int(year), int(month), int(day))
    return cur

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

ORDINAL_SUFFIX_RE = re.compile(r'(\d+)(st|nd|rd|th)\b', flags=re.I)

def _remove_ordinals(s: str) -> str:
    return ORDINAL_SUFFIX_RE.sub(r'\1', s)

def parse_date(text: str, base_date: get_current_date()) -> str | None:
    """
    Parse conversational date expressions into 'YYYY-MM-DD'.
    Returns ISO date string or None if not recognized.

    Assumptions:
      - Numeric dates like 26/11 are interpreted as DD/MM (day-first).
      - If year is missing, choose the nearest future occurrence (same year or next).
    """
    if not text or not text.strip():
        return None

    base = base_date
    s = _remove_ordinals(text.lower())
    s = s.replace(',', ' ').strip()

    # Quick keywords
    if re.search(r'\btoday\b', s):
        return base.isoformat()
    if re.search(r'\btomorrow\b', s):
        return (base + timedelta(days=1)).isoformat()
    if re.search(r'\bday after tomorrow\b', s) or re.search(r'\bafter tomorrow\b', s):
        return (base + timedelta(days=2)).isoformat()

    # Weekday handling: "next monday", "this fri", "monday"
    m = re.search(r'\b(?:(next|this)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thurs|fri|sat|sun)\b', s)
    if m:
        prefix, weekday_token = m.groups()
        wd_target = WEEKDAYS[weekday_token]
        cur_wd = base.weekday()
        days_ahead = (wd_target - cur_wd) % 7
        if prefix == 'next':
            days_ahead = days_ahead if days_ahead != 0 else 7
        elif prefix == 'this':
            # if "this monday" and today is monday -> 0 (today)
            days_ahead = days_ahead
        else:
            # bare weekday: prefer next occurrence (including today)
            days_ahead = days_ahead
        return (base + timedelta(days=days_ahead)).isoformat()

    # Month-name based parsing: "26 november", "nov 26", "26 november 2025"
    # Patterns to capture: day month (optional year) OR month day (optional year)
    m1 = re.search(r'\b(\d{1,2})\s+(?:of\s+)?([a-z]{3,9})(?:\s+(\d{4}|\d{2}))?\b', s)
    m2 = re.search(r'\b([a-z]{3,9})\s+(\d{1,2})(?:\s+(\d{4}|\d{2}))?\b', s)
    for mm in (m1, m2):
        if mm:
            if mm is m1:
                day_s, mon_s, year_s = mm.groups()
            else:
                mon_s, day_s, year_s = mm.groups()
            try:
                day = int(day_s)
                mon = MONTHS.get(mon_s[:3], None) if mon_s else None
                if mon is None:
                    mon = MONTHS.get(mon_s, None)
                if mon is None or not (1 <= day <= 31):
                    continue
                if year_s:
                    y = int(year_s)
                    if len(year_s) == 2:
                        # simple heuristic: 25 -> 2025
                        y += 2000
                else:
                    # infer year: choose the nearest future date (same year or next)
                    y = base.year
                    try:
                        candidate = date(y, mon, day)
                        if candidate < base:
                            y = y + 1
                    except Exception:
                        # invalid day (e.g., 31 Nov)
                        continue
                # validate and return
                d = date(y, mon, day)
                return d.isoformat()
            except Exception:
                continue

    # Numeric day/month[/year] - assume DD/MM(/YYYY)
    mnum = re.search(r'\b(\d{1,2})[\/\-\.\s](\d{1,2})(?:[\/\-\.\s](\d{2,4}))?\b', s)
    if mnum:
        d_s, m_s, y_s = mnum.groups()
        try:
            day = int(d_s)
            mon = int(m_s)
            if y_s:
                y = int(y_s)
                if len(y_s) == 2:
                    y += 2000
            else:
                y = base.year
                try:
                    candidate = date(y, mon, day)
                    if candidate < base:
                        y = y + 1
                except Exception:
                    # invalid numeric date for this year; try swapping day/month (rare)
                    # but we prefer day-first assumption — so fail
                    return None
            d = date(y, mon, day)
            return d.isoformat()
        except Exception:
            return None

    # ISO-like explicit year-month-day anywhere (already present)
    miso = re.search(r'(\d{4})[\/\-\.\s](\d{1,2})[\/\-\.\s](\d{1,2})', text)
    if miso:
        y, mo, da = miso.groups()
        try:
            d = date(int(y), int(mo), int(da))
            return d.isoformat()
        except Exception:
            return None

    return None

# assume today is 2025-11-20 (base)
base = get_current_date()

tests = [
    "26th november",
    "26 november",
    "Nov 26",
    "26 Nov 2026",
    "tomorrow",
    "day after tomorrow",
    "next monday",   # depends on base; function will produce the next monday date
    "on 26/11",
    "on 26-11-2025",
    "check availability on 26th november around 10 am", "2025-11-26",
]

def run_test(tests, base):
    for inp in tests:
        out = parse_date(inp, base_date=base)
        print(inp, "->", type(out))