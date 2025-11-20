# streamlit_agent_app.py
import streamlit as st
import json
from datetime import datetime
from run import conversational_run_agent  # expects (user_input, context) -> (reply, new_ctx)

# --------- Helpers for UI ----------
def ensure_session_state():
    if "conversation" not in st.session_state:
        st.session_state.conversation = []  # list of {"role":"user"/"assistant"/"system", "text":..., "time":...}
    if "agent_context" not in st.session_state:
        # context structure expected by your conversational_run_agent:
        # {"pending_action": None, "args": {}, "history": [], "booking_context": ...}
        st.session_state.agent_context = {"pending_action": None, "args": {}, "history": []}
    # make sure user_input key exists before any widget creation
    if "user_input" not in st.session_state:
        st.session_state.user_input = ""
    if "_processing" not in st.session_state:
        st.session_state._processing = False
    # storage for last slots presented (to show clickable UI)
    if "latest_slots" not in st.session_state:
        st.session_state.latest_slots = None

def append_message(role, text, meta=None):
    st.session_state.conversation.append({
        "role": role,
        "text": text,
        "meta": meta or {},
        "time": datetime.now().isoformat()
    })

def pretty_json(obj):
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        return str(obj)

# central handler calling conversational_run_agent
def handle_user_message(user_text):
    """
    Synchronous handler called from callbacks. Appends messages & updates context.
    If the agent returns a slots payload, store it to session_state.latest_slots so UI can render buttons.
    """
    append_message("user", user_text)
    try:
        reply, new_ctx = conversational_run_agent(user_text, st.session_state.agent_context)
    except Exception as e:
        append_message("system", f"Agent error: {e}")
        return

    st.session_state.agent_context = new_ctx or {"pending_action": None, "args": {}, "history": []}
    # Reset latest_slots unless set by this reply
    st.session_state.latest_slots = None

    # Try parsing reply as JSON
    parsed = None
    try:
        parsed = json.loads(reply)
    except Exception:
        parsed = None

    if parsed is not None and isinstance(parsed, dict):
        status = parsed.get("status")
        payload = parsed.get("payload") or parsed.get("slots") or parsed.get("event") or parsed.get("booking_context")

        # If it's a find_slots response with payload.slots
        if status in ("ok", "empty") and isinstance(parsed.get("payload"), dict):
            payload = parsed["payload"]
            slots = payload.get("slots", [])
            if slots:
                st.session_state.latest_slots = slots
                # Save a copy in agent_context so clicks can start booking flow
                st.session_state.agent_context.setdefault("last_shown_slots", slots)
                st.session_state.agent_context.setdefault("last_shown_date", payload.get("slot_date"))
                # Also remember this came from a "find_slots" action so clicking implies booking intention
                st.session_state.agent_context.setdefault("last_shown_origin", "find_slots")
                msg = parsed.get(
                    "message") or f"I found {len(slots)} slots for {payload.get('slot_date')}. Please select one."
                append_message("assistant", msg, meta=parsed)
                return

            else:
                msg = parsed.get("message") or parsed.get("error") or f"No slots found for {payload.get('slot_date') if payload else ''}."
                append_message("assistant", msg, meta=parsed)
                return

        # If booking confirmation (booked/failed), show nicely
        if status in ("booked", "failed"):
            human_msg = parsed.get("message") or (f"Booking {status}.")
            append_message("assistant", human_msg, meta=parsed)
            # Clear latest_slots on final booking
            st.session_state.latest_slots = None
            return

        # Generic structured response — show summary + JSON in details
        preview = status or parsed.get("summary") or "structured response"
        append_message("assistant", f"[{preview}] See details below.", meta=parsed)
        return

    # Not JSON — plain conversational reply string
    append_message("assistant", reply)

# --------- Helpers to match typed replies to slot indices ----------
import re
def match_text_to_slot_index(text, slots):
    """Return index of matching slot or None. Supports index, ordinal words, HH:MM, or time range text."""
    if not slots:
        return None
    u = text.strip().lower()
    # index
    m = re.search(r"\b(\d+)\b", u)
    if m:
        i = int(m.group(1)) - 1
        if 0 <= i < len(slots):
            return i
    # ordinals
    ord_map = {"first":0, "second":1, "third":2, "fourth":3, "fifth":4}
    for w, idx in ord_map.items():
        if w in u and idx < len(slots):
            return idx
    # time HH:MM
    mtime = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", u)
    if mtime:
        tm = mtime.group(0)
        for idx, s in enumerate(slots):
            if tm in s.get("start","") or tm in s.get("end",""):
                return idx
    # time range like '16:30 to 17:00' or '16:30-17:00', match start/time substring
    mrange = re.search(r"([01]?\d:[0-5]\d).{0,6}([01]?\d:[0-5]\d)", u)
    if mrange:
        start = mrange.group(1)
        for idx, s in enumerate(slots):
            if start in s.get("start",""):
                return idx
    # substring match (e.g., '16:30 to 17:00' contains '16:30')
    for idx, s in enumerate(slots):
        if any(part in u for part in [s.get("start","").lower(), s.get("end","").lower()]):
            return idx
    return None

# --------- Callbacks (must do all session_state writes here) ----------
def process_send_button():
    """Callback for Send button: read input, handle it, then clear input."""
    user_text = st.session_state.get("user_input", "").strip()
    if not user_text:
        return
    st.session_state._processing = True

    # If there are latest slots shown, try to match the typed reply to a slot first
    slots = st.session_state.latest_slots or []
    if slots:
        matched_idx = match_text_to_slot_index(user_text, slots)
        if matched_idx is not None:
            process_slot_selection(matched_idx)
            st.session_state.user_input = ""
            st.session_state._processing = False
            return

    # otherwise, normal message handling
    handle_user_message(user_text)
    st.session_state.user_input = ""
    st.session_state._processing = False

def quick_action_and_send(action_str):
    """Callback for quick-action buttons: set input and process immediately."""
    st.session_state._processing = True
    handle_user_message(action_str)
    st.session_state._processing = False
    st.session_state.user_input = ""

def process_slot_selection(slot_index: int):
    """
    Callback when user clicks a slot button.
    If agent is already in confirm_booking, send index to agent (existing flow).
    Otherwise, seed a booking intent (create_appointment_event) with selected slot's date/time
    and ask the LLM (via conversational_run_agent) to request any missing fields (e.g., patient_name).
    """
    slots = st.session_state.latest_slots or st.session_state.agent_context.get("last_shown_slots") or []
    if not (0 <= slot_index < len(slots)):
        # invalid click — ignore
        return

    chosen = slots[slot_index]
    start_iso = chosen.get("start")
    end_iso = chosen.get("end")

    # show which slot was clicked in UI as user's message (for UX)
    append_message("user", f"Selected slot: {start_iso} → {end_iso}")

    st.session_state._processing = True

    # If the conversational state is already waiting for confirmation booking, send a numeric reply (existing code)
    if st.session_state.agent_context.get("pending_action") == "confirm_booking":
        # existing flow: send numeric index so conversational_run_agent will map it to booking
        handle_user_message(str(slot_index + 1))
        st.session_state._processing = False
        # clear slots after selection only when booking is finalized or agent asks otherwise
        return

    # Otherwise: seed a create_appointment_event intent with the selected slot
    # Extract date and time parts (safe parse)
    try:
        date_part = start_iso.split("T")[0]
        time_part = start_iso.split("T")[1][:5]
    except Exception:
        date_part = st.session_state.agent_context.get("last_shown_date")
        # fallback: try extracting HH:MM from start_iso
        m = re.search(r"([01]?\d:[0-5]\d)", start_iso or "")
        time_part = m.group(1) if m else None

    # Seed the agent_context with partial args so the agent will ask for missing fields (like patient_name)
    ctx = st.session_state.agent_context
    ctx["pending_action"] = "create_appointment_event"
    ctx.setdefault("args", {})
    # Fill date/time (do not fill patient_name)
    ctx["args"]["date_str"] = date_part
    ctx["args"]["time_str"] = time_part
    # Also save a booking_context so agent can use it later when confirming
    ctx["booking_context"] = {
        "booking_meta": {
            # patient_name intentionally empty; agent will ask
            "patient_name": None,
            "description": "",
            "calendar_id": ctx.get("last_shown_origin_calendar", ctx.get("last_shown_calendar", "primary")),
            "duration_minutes": 30
        },
        "slots": slots,
        "requested_date": date_part,
    }
    st.session_state.agent_context = ctx

    # Now call agent with empty user_input to trigger the pending_action path.
    # conversational_run_agent will ask for missing fields (e.g., patient_name).
    try:
        reply, new_ctx = conversational_run_agent("", st.session_state.agent_context)
    except Exception as e:
        append_message("system", f"Agent error when seeding booking: {e}")
        st.session_state._processing = False
        return

    # update context and display the agent's follow-up (likely a question asking for name)
    st.session_state.agent_context = new_ctx or st.session_state.agent_context
    # show assistant reply (could be JSON or plain)
    try:
        parsed = json.loads(reply)
        # If agent returned JSON asking for slots etc., render friendly text
        msg = parsed.get("message") or parsed.get("error") or parsed.get("status") or str(parsed)
        append_message("assistant", msg, meta=parsed)
    except Exception:
        append_message("assistant", reply)

    st.session_state._processing = False
    # keep latest_slots around so user can still choose; do not clear them yet.

def clear_conversation_and_context():
    st.session_state.conversation = []
    st.session_state.agent_context = {"pending_action": None, "args": {}, "history": []}
    st.session_state.user_input = ""
    st.session_state.latest_slots = None

# --------- Streamlit UI layout ----------
st.set_page_config(page_title="Conversational Booking Agent", page_icon="🏥", layout="wide")
ensure_session_state()

# Small CSS tweaks: change assistant bubble color (darker so text is readable)
ASSISTANT_BUBBLE_STYLE = (
    "background:#1f2937;color:#ffffff;padding:12px;border-radius:10px;"
    "border-left:5px solid #2563eb;margin-bottom:6px;"
)
USER_BUBBLE_STYLE = "background:#e6f3ff;padding:10px;border-radius:8px;border-left:4px solid #ff6b6b;margin-bottom:6px;"
SYSTEM_BUBBLE_STYLE = "background:#fff3cd;padding:10px;border-radius:8px;border-left:4px solid #ffc107;margin-bottom:6px;"

st.markdown("<h1 style='text-align:center'>🏥 Conversational Booking Agent</h1>", unsafe_allow_html=True)

# Sidebar quick actions
with st.sidebar:
    st.header("Quick Actions")
    quick_actions = [
        "I want to book an appointment",
        "Find free slots for 2025-11-25",
        "Schedule a routine checkup",
        "I need to see a doctor tomorrow"
    ]
    for q in quick_actions:
        st.button(f"💬 {q}", key=f"quick_{q}", on_click=quick_action_and_send, args=(q,))

    st.markdown("---")
    st.write("Agent Context (debug)")
    st.write(st.session_state.agent_context)  # raw view for debugging
    if st.button("🔄 Clear Conversation & Context", on_click=clear_conversation_and_context):
        pass

# Main columns: conversation + details
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Conversation")
    # Render conversation messages
    for msg in st.session_state.conversation:
        if msg["role"] == "user":
            st.markdown(f"<div style='{USER_BUBBLE_STYLE}'><strong>You:</strong> {msg['text']}</div>", unsafe_allow_html=True)
        elif msg["role"] == "assistant":
            # Use the darker assistant bubble style for readability
            st.markdown(f"<div style='{ASSISTANT_BUBBLE_STYLE}'><strong>Agent:</strong> {msg['text']}</div>", unsafe_allow_html=True)
            if msg.get("meta"):
                with st.expander("Details (structured payload)"):
                    st.code(pretty_json(msg["meta"]), language="json")
        else:
            st.markdown(f"<div style='{SYSTEM_BUBBLE_STYLE}'><strong>System:</strong> {msg['text']}</div>", unsafe_allow_html=True)

    st.markdown("---")
    # Input area: text_input bound to session_state key (initialized earlier)
    col_in, col_send = st.columns([4,1])
    with col_in:
        user_input = st.text_input("Type your message:", key="user_input")
    with col_send:
        st.button("Send", on_click=process_send_button)

    # If there are latest slots, show them as buttons right below the input for quick selection
    if st.session_state.latest_slots:
        # In your Streamlit app
        st.markdown("**Available slots — click one to confirm**")
        for i, slot in enumerate(st.session_state.latest_slots):
            start = slot.get("start", "")
            end = slot.get("end", "")

            # Extract just the time portion from ISO format
            # "2025-11-25T10:00:00" -> "10:00"
            if "T" in start:
                start_time = start.split("T")[1][:5]  # Gets "10:00"
            else:
                start_time = start

            if "T" in end:
                end_time = end.split("T")[1][:5]  # Gets "10:30"
            else:
                end_time = end

            # Create button with just the time display
            st.button(
                f"{i + 1}. {start_time} → {end_time}",
                key=f"slot_{i}",
                on_click=process_slot_selection,
                args=(i,)
            )

with col_right:
    st.subheader("Agent Context & Debug")
    st.write("Pending action:", st.session_state.agent_context.get("pending_action"))
    st.write("Collected args:")
    st.json(st.session_state.agent_context.get("args", {}))
    st.write("History excerpt (last 3):")
    hist = st.session_state.agent_context.get("history", [])[-3:]
    for h in hist:
        st.write(f"- {h.get('time','')}: {h.get('content','')}")

    st.markdown("---")
    st.subheader("Raw Conversation JSON")
    st.code(pretty_json(st.session_state.conversation), language="json")
