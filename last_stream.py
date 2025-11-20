# streamlit_agent_app.py
import streamlit as st
import json
from datetime import datetime
from run import conversational_run_agent


# --------- Helpers for UI ----------
def ensure_session_state():
    if "conversation" not in st.session_state:
        st.session_state.conversation = []
    if "agent_context" not in st.session_state:
        st.session_state.agent_context = {"pending_action": None, "args": {}, "history": []}
    if "user_input" not in st.session_state:
        st.session_state.user_input = ""
    if "_processing" not in st.session_state:
        st.session_state._processing = False
    if "latest_slots" not in st.session_state:
        st.session_state.latest_slots = None


def append_message(role, text):
    st.session_state.conversation.append({
        "role": role,
        "text": text,
        "time": datetime.now().isoformat()
    })


def handle_user_message(user_text):
    """Process user message and get agent response"""
    append_message("user", user_text)
    try:
        reply, new_ctx = conversational_run_agent(user_text, st.session_state.agent_context)
    except Exception as e:
        append_message("assistant", f"I apologize, but I encountered an error. Please try again.")
        return

    st.session_state.agent_context = new_ctx or {"pending_action": None, "args": {}, "history": []}
    st.session_state.latest_slots = None

    # Try parsing reply as JSON for slot data
    parsed = None
    try:
        parsed = json.loads(reply)
    except Exception:
        parsed = None

    if parsed is not None and isinstance(parsed, dict):
        status = parsed.get("status")
        payload = parsed.get("payload") or parsed.get("slots") or parsed.get("event") or parsed.get("booking_context")

        # Handle slot responses
        if status in ("ok", "empty") and isinstance(parsed.get("payload"), dict):
            payload = parsed["payload"]
            slots = payload.get("slots", [])
            if slots:
                st.session_state.latest_slots = slots
                st.session_state.agent_context.setdefault("last_shown_slots", slots)
                st.session_state.agent_context.setdefault("last_shown_date", payload.get("slot_date"))
                msg = f"I found {len(slots)} available slots for {payload.get('slot_date')}. Please select one below."
                append_message("assistant", msg)
                return
            else:
                msg = f"No available slots found for {payload.get('slot_date')}. Would you like to check another date?"
                append_message("assistant", msg)
                return

        # Handle booking responses
        if status in ("booked", "failed"):
            human_msg = parsed.get("message") or (f"Booking {status}.")
            append_message("assistant", human_msg)
            st.session_state.latest_slots = None
            return

        # Generic structured response
        preview = status or parsed.get("summary") or "I have some information for you"
        append_message("assistant", preview)
        return

    # Plain text response
    append_message("assistant", reply)


# --------- Slot matching ----------
import re


def match_text_to_slot_index(text, slots):
    """Return index of matching slot or None"""
    if not slots:
        return None
    u = text.strip().lower()

    # Match numeric index
    m = re.search(r"\b(\d+)\b", u)
    if m:
        i = int(m.group(1)) - 1
        if 0 <= i < len(slots):
            return i

    # Match time HH:MM
    mtime = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", u)
    if mtime:
        tm = mtime.group(0)
        for idx, s in enumerate(slots):
            if tm in s.get("start", "") or tm in s.get("end", ""):
                return idx

    return None


# --------- Callbacks ----------
def process_send_button():
    """Callback for Send button"""
    user_text = st.session_state.get("user_input", "").strip()
    if not user_text:
        return
    st.session_state._processing = True

    # Try to match text to slot if slots are shown
    slots = st.session_state.latest_slots or []
    if slots:
        matched_idx = match_text_to_slot_index(user_text, slots)
        if matched_idx is not None:
            process_slot_selection(matched_idx)
            st.session_state.user_input = ""
            st.session_state._processing = False
            return

    # Normal message handling
    handle_user_message(user_text)
    st.session_state.user_input = ""
    st.session_state._processing = False


def quick_action_and_send(action_str):
    """Callback for quick-action buttons"""
    st.session_state._processing = True
    handle_user_message(action_str)
    st.session_state._processing = False
    st.session_state.user_input = ""


def process_slot_selection(slot_index: int):
    """Callback when user clicks a slot button"""
    slots = st.session_state.latest_slots or st.session_state.agent_context.get("last_shown_slots") or []
    if not (0 <= slot_index < len(slots)):
        return

    chosen = slots[slot_index]
    start_iso = chosen.get("start")
    end_iso = chosen.get("end")

    # Show selected slot in conversation
    if "T" in start_iso:
        start_time = start_iso.split("T")[1][:5]
        end_time = end_iso.split("T")[1][:5] if "T" in end_iso else end_iso
        display_text = f"Selected slot: {start_time} - {end_time}"
    else:
        display_text = f"Selected slot: {start_iso} → {end_iso}"

    append_message("user", display_text)
    st.session_state._processing = True

    # If already in booking flow, send index
    if st.session_state.agent_context.get("pending_action") == "confirm_booking":
        handle_user_message(str(slot_index + 1))
        st.session_state._processing = False
        return

    # Start booking flow with selected slot
    try:
        date_part = start_iso.split("T")[0]
        time_part = start_iso.split("T")[1][:5]
    except Exception:
        date_part = st.session_state.agent_context.get("last_shown_date")
        m = re.search(r"([01]?\d:[0-5]\d)", start_iso or "")
        time_part = m.group(1) if m else None

    ctx = st.session_state.agent_context
    ctx["pending_action"] = "create_appointment_event"
    ctx.setdefault("args", {})
    ctx["args"]["date_str"] = date_part
    ctx["args"]["time_str"] = time_part

    st.session_state.agent_context = ctx

    # Trigger agent to ask for missing info
    try:
        reply, new_ctx = conversational_run_agent("", st.session_state.agent_context)
        st.session_state.agent_context = new_ctx or st.session_state.agent_context
        append_message("assistant", reply)
    except Exception as e:
        append_message("assistant", "I apologize, but I encountered an error. Please try again.")

    st.session_state._processing = False


def clear_conversation():
    st.session_state.conversation = []
    st.session_state.agent_context = {"pending_action": None, "args": {}, "history": []}
    st.session_state.user_input = ""
    st.session_state.latest_slots = None


# --------- Streamlit UI ----------
st.set_page_config(page_title="Medical Appointment Agent", page_icon="🏥", layout="wide")
ensure_session_state()

# Custom CSS for better appearance
st.markdown("""
<style>
    .assistant-bubble {
        background: #1f2937;
        color: white;
        padding: 12px;
        border-radius: 10px;
        border-left: 5px solid #2563eb;
        margin-bottom: 10px;
    }
    .user-bubble {
        background: #e6f3ff;
        padding: 12px;
        border-radius: 10px;
        border-left: 4px solid #ff6b6b;
        margin-bottom: 10px;
    }
    .slot-button {
        width: 100%;
        margin: 2px 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center'>🏥 Medical Appointment Assistant</h1>", unsafe_allow_html=True)

# Sidebar with quick actions
with st.sidebar:
    st.header("Quick Actions")
    quick_actions = [
        "Book an appointment",
        "Find available slots",
        "Schedule a checkup",
        "See available times"
    ]
    for q in quick_actions:
        st.button(f"💬 {q}", key=f"quick_{q}", on_click=quick_action_and_send, args=(q,))

    st.markdown("---")
    if st.button("🗑️ Clear Conversation", on_click=clear_conversation, use_container_width=True):
        st.success("Conversation cleared!")

# Main conversation area
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Conversation")

    # Display conversation
    for msg in st.session_state.conversation:
        if msg["role"] == "user":
            st.markdown(f"<div class='user-bubble'><strong>You:</strong> {msg['text']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='assistant-bubble'><strong>Assistant:</strong> {msg['text']}</div>",
                        unsafe_allow_html=True)

    # Input area
    st.markdown("---")
    input_col1, input_col2 = st.columns([4, 1])
    with input_col1:
        user_input = st.text_input("Type your message:", key="user_input",
                                   placeholder="Ask about appointments or type your message...")
    with input_col2:
        st.button("Send", on_click=process_send_button, use_container_width=True)

    # Available slots as buttons
    if st.session_state.latest_slots:
        st.markdown("### 🕒 Available Time Slots")
        st.markdown("Click on a time slot to book:")

        # Create columns for slots (2 per row for better layout)
        slots = st.session_state.latest_slots
        cols = st.columns(2)

        for i, slot in enumerate(slots):
            col = cols[i % 2]
            start_iso = slot.get("start", "")
            end_iso = slot.get("end", "")

            if "T" in start_iso:
                start_time = start_iso.split("T")[1][:5]
                end_time = end_iso.split("T")[1][:5] if "T" in end_iso else end_iso
                button_text = f"{start_time} - {end_time}"
            else:
                button_text = f"Slot {i + 1}"

            col.button(
                button_text,
                key=f"slot_{i}",
                on_click=process_slot_selection,
                args=(i,),
                use_container_width=True
            )

with col2:
    st.subheader("About")
    st.markdown("""
    **How to use:**
    - 💬 Use quick actions to get started
    - 📅 Ask about available time slots
    - ⏰ Click time slots to book instantly
    - ✅ Confirm details when prompted

    This assistant can help you:
    - Find available appointment slots
    - Book medical appointments
    - Schedule checkups and consultations
    """)

    if st.session_state.latest_slots:
        st.info(f"🎯 {len(st.session_state.latest_slots)} slots available")

    if st.session_state.agent_context.get("pending_action"):
        action = st.session_state.agent_context["pending_action"]
        friendly_action = "Finding slots" if action == "find_free_slots" else "Booking appointment"
        st.info(f"**Current task:** {friendly_action}")