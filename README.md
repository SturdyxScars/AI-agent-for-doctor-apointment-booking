# Doctor Booking Agent

A lightweight conversational booking agent for scheduling appointments with a doctor's Google Calendar. Built around an LLM assistant (OllamaLLM in the example) and utility functions that integrate with Google Calendar.

---

## Quick summary

* Purpose: Let patients/conversational users check availability and book appointments via natural language.
* Core idea: Use an LLM to parse user intent and dates/times, then call deterministic helper functions to query Google Calendar and create events.
* Minimal dependencies: an LLM client, `googleapiclient`-style calendar helpers, and a small Streamlit UI for demonstrations.

---

## Folder structure

```
- Booking_Agent.py        # conversational workflow and state-machine for booking
- calendar_functions.py   # Google Calendar helper functions (query/free slots/create event)
- google_apis.py          # OAuth helper for doctor to create & store credentials
- doctor-agent-UI.py      # Streamlit UI that shows chat and lets users choose time slots
- LLM_prompts.py         # prompts and system instructions used by the LLM
```

---

## Installation

1. Create a Python virtual environment and activate it.

```bash
python -m venv venv
source venv/bin/activate  # macOS / Linux
venv\Scripts\activate     # Windows
```

2. Install required packages (example list — adjust to your project):

```bash
pip install langchain_ollama google-auth google-auth-oauthlib google-api-python-client streamlit python-dateutil
```

3. Place your Google Cloud `client_secret.json` (OAuth 2.0 credentials) in the project root or a secure folder. See **Google API Setup** below.

---

## Google API setup (doctor / calendar owner)

1. Go to Google Cloud Console → APIs & Services → Credentials.
2. Create OAuth 2.0 Client ID for a "Desktop" or "Web" application depending on your deployment.
3. Download `client_secret.json` and save it in the project root (or update the path in code).
4. Run the OAuth helper flow in `google_apis.py` to generate and store the token/credentials the first time.

> `calendar_service = construct_calendar_service("client_secret.json")` in `Booking_Agent.py` expects `construct_calendar_service` to return an authorized `service` object for Calendar API calls.

---

## How the BookingAgent works (high level)

`Booking_Agent.py` implements a simple state machine that orchestrates conversational booking.

States:

* `idle`: Default. Waits for user input and detects whether it's a scheduling request.
* `awaiting_date`: A scheduling request has been detected. The agent attempts to parse a date (via LLM or heuristics) and will call `find_free_slots_for_date`.
* `slots_found`: Available time slots have been retrieved and presented to the user; agent awaits slot selection.
* `booking-details`: (implicit) After a slot is selected, the agent gathers patient details (name, reason) if needed.
* `completed`: Appointment created and agent resets.

Key pieces:

* `self.FUNCTIONS`: deterministic helper functions the LLM can ask to call: `parse_date`, `get_current_date`, `find_free_slots_for_date`, `create_appointment_event`.
* `extract_json`: lightweight JSON extraction from model responses (expects the LLM to return JSON when asked to call functions).
* `_heuristic_parse_date`: quick deterministic fallback for common words/dates (today, tomorrow, weekdays, numeric patterns).
* `_find_available_slots`: calls calendar function, converts results to human-friendly `HH:MM-HH:MM` tuples and sets `self.available_slots`.
* `_handle_booking_creation`: finalizes booking by calling `create_appointment_event` and returns a success/failure message.

### Important behavior notes

* The agent uses the LLM for date parsing and extracting booking details, but it always calls deterministic calendar functions to read/write the calendar.
* After a successful booking the agent calls `reset()` which returns it to `idle` and clears context.
* If the LLM fails to return expected JSON or actions, the agent falls back to generating conversational prompts to ask the user for missing information.

---

## Running the Streamlit UI

`doctor-agent-UI.py` is a demo UI to simulate chat with the BookingAgent and to present available slots as clickable items.

Run it with:

```bash
streamlit run doctor-agent-UI.py
```

The UI should:

* Display conversational history
* Let a user choose a suggested time slot (the UI can set `context['time_str']` accordingly)
* Forward chat text to the agent and render agent replies

---

## Prompts and LLM behavior

All prompt templates used to parse dates, request slots, and collect booking details are in `LLM_prompts.py`.

Design notes for LLM prompts:

* Keep the LLM's role focused (date parsing, slot-finding, or extracting patient info).
* When you want the LLM to return structured data or call functions, instruct it to return strict JSON and provide a schema example.
* Always have deterministic fallback code paths (`_heuristic_parse_date` and regex heuristics) when the LLM returns malformed JSON.

---

## calendar_functions.py expectations

`find_free_slots_for_date(service, calendar_id, date_str, ...)` should:

* Query the Calendar API for events on the given date
* Return a structure where the third element (index `2`) is a list of `(start_datetime, end_datetime)` tuples that represent free slots, which `BookingAgent.parse_time_slots_as_tuples` expects.

`create_appointment_event(service, calendar_id, patient_name, date_str, time_str, description)` should:

* Create a Calendar event on the requested date/time and return the created event object or raise an error.

Adjust signatures and return formats if your `calendar_functions.py` uses slightly different shapes — update `parse_time_slots_as_tuples` accordingly.

---

## Example conversation flow

1. User: "Do you have any slots tomorrow morning?"
2. Agent detects scheduling intent → `awaiting_date` → parse date (LLM or heuristics) → call `find_free_slots_for_date`.
3. Agent replies with a compact list of available times and asks the user to choose.
4. User: "Let's do 09:30–10:00"
5. Agent marks `context['time_str']` and moves to booking creation, asking for name/reason if not provided.
6. Agent calls `create_appointment_event` and confirms success or reports failure.

---

## Testing and debugging

* Use prints and logs in the agent (`print(f"DEBUG: ...")`) to trace state transitions and LLM raw outputs.
* Provide deterministic tests by mocking LLM responses and calendar function outputs.
* Validate `extract_json` behavior with varied LLM responses (multiline JSON, extra commentary around JSON, missing JSON).

---

## Extending this agent

* Add timezone-aware handling (store timezone in calendar calls and normalize all datetimes).
* Implement a richer `slots_found` flow where the user can ask for "earlier/later", or the agent can propose next-best slots.
* Add authentication and user profiles so returning patients can book without re-entering name/details.
* Persist conversation logs and booking metadata for analytics and audit.

---

## Security and privacy

* Never commit `client_secret.json` or token files to source control.
* If deployed publicly, secure OAuth client secrets in environment variables or a secrets manager.
* You are writing medical appointment data to a calendar — make sure you comply with local privacy regulations (HIPAA, GDPR etc.) when storing protected health information.

---

## Contributing

Feel free to open issues or pull requests. For changes to calendar behavior, include unit tests that mock Google Calendar responses.

## Demo


https://github.com/user-attachments/assets/8f0ed289-68ea-4e71-a464-80e719d7547a


