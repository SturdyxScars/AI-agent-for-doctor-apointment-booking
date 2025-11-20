# conversational_agent.py (patched)
import json
import re
from datetime import datetime, date
from datetime import datetime as dt

from langchain_ollama.llms import OllamaLLM

from calendar_demo import (
    find_free_slots_for_date,
    create_appointment_event,
    construct_calendar_service,
)

# ----- Configuration -----
service = construct_calendar_service("./LLM_agent/client_secret.json")
# Use deterministic temperature for structured JSON outputs
llm = OllamaLLM(model="llama3.2", temperature=0)
DEFAULT_CALENDAR_ID = "primary"


# ----- Utilities -----
def extract_json(text: str):
    """Extract JSON from LLM response"""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def make_json_safe(obj):
    """Make objects JSON serializable"""
    from datetime import date, datetime as dt
    if obj is None:
        return None
    if isinstance(obj, (dt, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [make_json_safe(v) for v in obj]
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


REQUIRED_FIELDS = {
    "find_free_slots": ["date_str"],
    "create_appointment_event": ["patient_name", "date_str", "time_str"],
}


def missing_fields_for_action(action_name, args):
    """Check which required fields are missing"""
    req = REQUIRED_FIELDS.get(action_name, [])
    missing = [f for f in req if not args.get(f)]
    return missing


def ask_for_fields(missing_fields):
    """Generate natural language prompts for missing fields"""
    prompts = {
        "patient_name": "What's the patient's full name?",
        "date_str": "Which date would you like (YYYY-MM-DD)?",
        "time_str": "What start time would you prefer (HH:MM, 24-hour)?",
    }
    if len(missing_fields) == 1:
        return prompts.get(missing_fields[0], f"Please provide {missing_fields[0]}.")
    else:
        q_parts = [prompts.get(f, f"{f}") for f in missing_fields]
        return "I need a few details: " + " ".join(q_parts)


# --- Rule-based quick extractor (cheap and deterministic) ---
def rule_based_intent(user_input: str):
    """Return a small intent dict or None if not confident.

    Possible return shapes:
      {'action': 'find_free_slots', 'args': {'date_str': 'YYYY-MM-DD'}}
      {'action': 'create_appointment_event', 'args': {'patient_name': ..., 'date_str': ..., 'time_str': ...}}
    """
    u = user_input.strip()
    if not u:
        return None
    lower = u.lower()

    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', user_input)
    time_match = re.search(r'\b([01]?\d|2[0-3]):[0-5]\d\b', user_input)
    slot_num_match = re.search(r'\b(?:slot\s*)?([1-9][0-9]?)\b', user_input)
    name_match = re.search(r'(?:patient name|patient is|my name|name is)\s+([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+){0,3})', user_input)

    wants_slots = any(k in lower for k in ["find free slots", "free slots", "available slots", "check for", "find slots", "find free"]) or ("find" in lower and "slots" in lower)
    wants_book = any(k in lower for k in ["book", "schedule", "reserve", "i want to book", "book an appointment", "please book"]) or "appointment" in lower

    # If user asked explicitly for slots
    if wants_slots or (date_match and not wants_book):
        args = {}
        if date_match:
            args["date_str"] = date_match.group(1)
        return {"action": "find_free_slots", "args": args}

    # If user asked to book or provided name+date
    if wants_book or (name_match and date_match):
        args = {}
        if name_match:
            args["patient_name"] = name_match.group(1).strip()
        if date_match:
            args["date_str"] = date_match.group(1)
        if time_match:
            args["time_str"] = time_match.group(0)
        if slot_num_match and not args.get("time_str"):
            args["slot_index"] = int(slot_num_match.group(1)) - 1
        return {"action": "create_appointment_event", "args": args}

    return None


def _execute_action(ctx, user_input=""):
    """Execute the current pending action with collected args"""
    action_name = ctx.get("pending_action")
    args = ctx.get("args", {})

    if action_name == "find_free_slots":
        date_str = args.get("date_str")
        calendar_id = args.get("calendar_id") or DEFAULT_CALENDAR_ID
        work_start = args.get("work_start") or "09:00"
        work_end = args.get("work_end") or "17:00"
        slot_minutes = int(args.get("slot_minutes", 30))
        max_days_ahead = int(args.get("max_days_ahead", 3))

        # validate date_str
        try:
            dt.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return ("Please provide a valid date in YYYY-MM-DD format.", ctx)

        def attempt_search(slot_minutes_try, max_days_try):
            try:
                return True, find_free_slots_for_date(
                    service,
                    date_str=date_str,
                    calendar_id=calendar_id,
                    work_start=work_start,
                    work_end=work_end,
                    slot_minutes=slot_minutes_try,
                    max_days_ahead=max_days_try,
                )
            except Exception as e:
                return False, e

        # first attempt
        ok, res = attempt_search(slot_minutes, max_days_ahead)
        if not ok:
            print("DEBUG: find_free_slots_for_date failed (first attempt):", repr(res))
            # try a relaxed search
            try_slot = max(30, slot_minutes * 2)
            try_max_days = max(0, max_days_ahead - 1)
            ok2, res2 = attempt_search(try_slot, try_max_days)
            if not ok2:
                print("DEBUG: find_free_slots_for_date failed (retry):", repr(res2))
                return (
                    f"Sorry — I couldn't compute free slots for {date_str}. This can happen if calendar constraints or permissions prevent checking availability. Would you like me to try a different date or relax the constraints?",
                    ctx,
                )
            else:
                slot_date, hours, free_slots = res2
        else:
            slot_date, hours, free_slots = res

        slots_serializable = [{"start": s.isoformat(), "end": e.isoformat()} for s, e in (free_slots or [])]

        # Format slots for display
        slot_display = []
        for i, slot in enumerate(slots_serializable):
            start_time = slot["start"][11:16] if "T" in slot["start"] else slot["start"]
            end_time = slot["end"][11:16] if "T" in slot["end"] else slot["end"]
            slot_display.append(f"{i + 1}. {start_time} - {end_time}")

        enumerated = "\n".join(slot_display)

        # Store slots in context
        ctx["available_slots"] = slots_serializable
        ctx["args"]["date_str"] = date_str
        ctx["pending_action"] = None

        if not slots_serializable:
            return (f"No available slots found for {date_str}. Would you like to check another date?", ctx)
        else:
            return (
                f"I found {len(slots_serializable)} available slots for {date_str}:\n\n{enumerated}\n\nWould you like to book one of these?",
                ctx,
            )

    elif action_name == "create_appointment_event":
        # Confirmation flow
        if ctx.get("needs_confirmation"):
            if user_input.strip().lower() in ["yes", "confirm", "y", "ok", "yes please"]:
                patient_name = args.get("patient_name")
                date_str = args.get("date_str")
                time_str = args.get("time_str")
                description = args.get("description", "")
                calendar_id = args.get("calendar_id") or DEFAULT_CALENDAR_ID
                duration_minutes = int(args.get("duration_minutes", 30))

                try:
                    event_res = create_appointment_event(
                        service=service,
                        patient_name=patient_name,
                        date_str=date_str,
                        time_str=time_str,
                        description=description,
                        calendar_id=calendar_id,
                        duration_minutes=duration_minutes,
                    )

                    safe_event = make_json_safe(event_res)

                    # Clear context after booking
                    ctx["pending_action"] = None
                    ctx["args"] = {}
                    ctx.pop("available_slots", None)
                    ctx.pop("needs_confirmation", None)

                    return (f"✅ Appointment confirmed for {patient_name} on {date_str} at {time_str}!", ctx)

                except Exception as e:
                    print("DEBUG: create_appointment_event failed:", repr(e))
                    return (f"Sorry, booking failed: {e}", ctx)
            else:
                ctx["pending_action"] = None
                ctx["args"] = {}
                ctx.pop("needs_confirmation", None)
                return ("Booking cancelled. Let me know if you need anything else!", ctx)
        else:
            # Show confirmation before booking
            patient_name = args.get("patient_name")
            date_str = args.get("date_str")
            time_str = args.get("time_str")

            ctx["needs_confirmation"] = True

            return (
                f"Please confirm the appointment details:\n"
                f"• Patient: {patient_name}\n"
                f"• Date: {date_str}\n"
                f"• Time: {time_str}\n\n"
                f"Type 'yes' to confirm or 'no' to cancel.",
                ctx,
            )

    return ("Action completed.", ctx)


# -----------------------
# Main conversational agent
# -----------------------
def conversational_run_agent(user_input: str, context: dict):
    """Simplified conversational agent that leverages LLM intelligence for parsing.

    Returns: (reply_text, updated_context)
    """
    ctx = context.copy() if context else {}
    ctx.setdefault("pending_action", None)
    ctx.setdefault("args", {})
    ctx.setdefault("history", [])
    ctx.setdefault("available_slots", [])
    ctx.setdefault("needs_confirmation", None)

    # Add to history
    ctx["history"].append({"role": "user", "content": user_input, "time": datetime.now().isoformat()})

    # 0) Handle confirmation state FIRST
    if ctx.get("needs_confirmation"):
        return _execute_action(ctx, user_input)

    # 1) Handle slot selection from previous search or "yes/book" responses
    if ctx.get("available_slots") and any(word in user_input.lower() for word in ["yes", "book", "schedule", "reserve"]):
        ctx["pending_action"] = "create_appointment_event"

        if ctx["args"].get("date_str"):
            time_match = re.search(r'\b([01]?\d|2[0-3]):[0-5]\d\b', user_input)
            number_match = re.search(r'\b(?:slot\s*)?(\d{1,2})\b', user_input)

            if time_match:
                ctx["args"]["time_str"] = time_match.group(0)
                return ("Great — I have the time. What's the patient's full name?", ctx)
            elif number_match:
                idx = int(number_match.group(1)) - 1
                if 0 <= idx < len(ctx["available_slots"]):
                    iso_start = ctx["available_slots"][idx]["start"]
                    ctx["args"]["time_str"] = iso_start[11:16] if "T" in iso_start else iso_start
                    return ("Great — slot reserved tentatively. What's the patient's full name?", ctx)
                else:
                    return ("That slot number is out of range. Please specify a slot number or time from the list.", ctx)
            else:
                return ("Great! Let's book your appointment. What's the patient's name and preferred time?", ctx)
        else:
            return ("Great! Let's book your appointment. What's the patient's name, date, and preferred time?", ctx)

    # 2) If we have a pending action, let LLM extract missing fields (with regex fallback)
    if ctx["pending_action"]:
        extractor_prompt = f"""
        You are a medical appointment assistant. The user is currently in the process of: {ctx['pending_action']}

        Already collected information:
        {json.dumps(ctx['args'], indent=2)}

        Extract ONLY the missing required information from the user's latest message.
        Required fields for {ctx['pending_action']}: {REQUIRED_FIELDS.get(ctx['pending_action'], [])}

        Return a JSON object with any new fields you extract. Only include fields the user explicitly provided.
        If no relevant information is provided, return an empty object {{}}.

        User's message: "{user_input}"
        """

        try:
            extract_reply = llm.invoke(extractor_prompt)
            parsed = extract_json(extract_reply) or {}

            # Fallback regex extraction if LLM didn't return valid JSON
            if not parsed:
                name_match = re.search(r"(?:patient name|my name|name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})", user_input)
                if name_match:
                    parsed["patient_name"] = name_match.group(1).strip()

                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', user_input)
                if date_match:
                    parsed["date_str"] = date_match.group(1)

                time_match = re.search(r'\b([01]?\d|2[0-3]):[0-5]\d\b', user_input)
                if time_match:
                    parsed["time_str"] = time_match.group(0)

            print("DEBUG: Extracted fields:", parsed)
        except Exception as e:
            print("DEBUG: Extraction failed:", repr(e))
            parsed = {}

        # Merge extracted fields
        ctx["args"].update(parsed)

        # Check if we have everything needed
        missing = missing_fields_for_action(ctx["pending_action"], ctx["args"])
        if missing:
            return (ask_for_fields(missing), ctx)

        # If we have all fields, execute the action
        return _execute_action(ctx, user_input)

    # 3) No pending action - try rule-based first, then LLM
    rule_decision = rule_based_intent(user_input)
    if rule_decision:
        action_name = rule_decision["action"]
        supplied_args = rule_decision.get("args", {})

        # Map slot_index to time_str if available
        if "slot_index" in supplied_args:
            idx = supplied_args.pop("slot_index")
            if ctx.get("available_slots") and 0 <= idx < len(ctx["available_slots"]):
                iso_start = ctx["available_slots"][idx]["start"]
                supplied_args["time_str"] = iso_start[11:16] if "T" in iso_start else iso_start

        ctx["args"].update(supplied_args)
        missing = missing_fields_for_action(action_name, ctx["args"])
        if missing:
            ctx["pending_action"] = action_name
            return (ask_for_fields(missing), ctx)
        ctx["pending_action"] = action_name
        return _execute_action(ctx, user_input)

    # Fallback to LLM for harder cases
    decision_prompt = f"""
    You are a medical appointment assistant. Analyze the user's intent and extract relevant information.

    Possible actions:
    - find_free_slots: Check available appointment slots (requires date_str)
    - create_appointment_event: Book an appointment (requires patient_name, date_str, time_str)
    - chat: Casual conversation

    Return JSON with one of these formats:
    {{"action": "find_free_slots", "args": {{"date_str": "2025-11-25"}}}}
    {{"action": "create_appointment_event", "args": {{"patient_name": "John Doe", "date_str": "2025-11-25", "time_str": "14:30"}}}}
    {{"response": "Your friendly reply here"}} for casual conversation

    Extract only the information the user explicitly provides. Don't invent values.
    Be precise with dates (YYYY-MM-DD) and times (HH:MM).

    User: "{user_input}"
    """

    try:
        decision_reply = llm.invoke(decision_prompt)
        print("DEBUG: LLM decision raw:\n", decision_reply)
        decision_data = extract_json(decision_reply) or {}
        print("DEBUG: Decision data:", decision_data)
    except Exception as e:
        print("DEBUG: Decision failed:", repr(e))
        decision_data = {}

    # Handle casual chat
    if "response" in decision_data:
        return (decision_data["response"], ctx)

    # Handle actions
    if "action" in decision_data:
        action_name = decision_data["action"]
        supplied_args = decision_data.get("args", {})

        # Merge arguments
        ctx["args"].update(supplied_args)

        # Check for missing fields
        missing = missing_fields_for_action(action_name, ctx["args"])
        if missing:
            ctx["pending_action"] = action_name
            return (ask_for_fields(missing), ctx)

        # All fields present - execute action
        ctx["pending_action"] = action_name
        return _execute_action(ctx, user_input)

    # Fallback response
    return ("I'm not sure what you'd like to do. Would you like to find available slots or book an appointment?", ctx)


# -----------------------
# Test function
# -----------------------
def run_simulation(messages):
    ctx = {"pending_action": None, "args": {}, "history": [], "available_slots": []}
    print("\n--- START SIMULATION ---\n")
    for i, msg in enumerate(messages, 1):
        print(f">>> USER ({i}): {msg}")
        reply, ctx = conversational_run_agent(msg, ctx)
        print(f"<<< AGENT ({i}): {reply}\n")
        print(f"Context: pending_action={ctx.get('pending_action')}, args={ctx.get('args')}")
        print("-" * 50)
    print("--- END SIMULATION ---\n")
    return ctx


if __name__ == "__main__":
    test_conversation = [
        "Hello!",
        "I want to find free slots for 2025-11-26",
        "Yes, please book for me",
        "My name is Alice Johnson and I want 10:30",
        "yes",
    ]
    run_simulation(test_conversation)
