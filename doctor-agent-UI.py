import streamlit as st
from Booking_Agent_class import BookingAgent, OllamaLLM

st.set_page_config(
    page_title="MediBook Pro - Healthcare Scheduling",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
        color: #f8fafc;
    }

    /* Main Header */
    .main-header {
        font-size: 3.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
        padding: 1rem;
        text-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
    }

    .sub-header {
        font-size: 1.3rem;
        color: #cbd5e1;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 400;
        letter-spacing: 0.5px;
    }

    /* Enhanced Chat Container */
    .chat-main-container {
        background: rgba(255, 255, 0, 0.02);
        backdrop-filter: blur(20px);
        border-radius: 24px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        padding: 0;
        overflow: hidden;
        height: 100px;
        display: flex;
        flex-direction: column;
        flex: 1;
        padding: 1.5rem 2rem;
        overflow-y: auto;
        max-height: 400px;
    }

    .chat-header {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        padding: 1.5rem 2rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .chat-messages-container {
        flex: 1;
        padding: 1.5rem 2rem;
        overflow-y: auto;
        max-height: 400px;
    }

    .chat-input-container {
        padding: 1.5rem 2rem;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        background: rgba(255, 255, 255, 0.02);
    }

    /* Enhanced Message Bubbles */
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 18px 18px 4px 18px;
        margin: 0.8rem 0;
        max-width: 80%;
        margin-left: auto;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.15);
        position: relative;
        animation: slideInRight 0.3s ease-out;
    }

    .assistant-message {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
        color: #f8fafc;
        padding: 1rem 1.5rem;
        border-radius: 18px 18px 18px 4px;
        margin: 0.8rem 0;
        max-width: 80%;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.08);
        animation: slideInLeft 0.3s ease-out;
    }

    @keyframes slideInRight {
        from { transform: translateX(30px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }

    @keyframes slideInLeft {
        from { transform: translateX(-30px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }

    /* Enhanced Input Area */
    .enhanced-input-container {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(20px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1.5rem;
        margin-top: 1.5rem;
    }

    .input-with-button {
        display: flex;
        gap: 12px;
        align-items: flex-end;
    }

    /* Enhanced Time Slot Buttons */
    .slots-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 12px;
        margin: 1.5rem 0;
        padding: 1.5rem;
        background: rgba(255, 255, 255, 0.02);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }

    .slot-btn {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        border: none;
        padding: 1rem 1.2rem;
        border-radius: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
        text-align: center;
        position: relative;
        overflow: hidden;
    }

    .slot-btn:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(16, 185, 129, 0.4);
    }

    /* Status Indicators */
    .status-pill {
        display: inline-flex;
        align-items: center;
        padding: 0.7rem 1.5rem;
        border-radius: 50px;
        font-weight: 600;
        margin-bottom: 1rem;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }

    .status-ready {
        background: linear-gradient(135deg, rgba(21, 128, 61, 0.2) 0%, rgba(34, 197, 94, 0.1) 100%);
        color: #4ade80;
        border-color: rgba(74, 222, 128, 0.3);
    }

    .status-awaiting {
        background: linear-gradient(135deg, rgba(180, 83, 9, 0.2) 0%, rgba(245, 158, 11, 0.1) 100%);
        color: #fbbf24;
        border-color: rgba(251, 191, 36, 0.3);
    }

    .status-active {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.2) 0%, rgba(59, 130, 246, 0.1) 100%);
        color: #60a5fa;
        border-color: rgba(96, 165, 250, 0.3);
    }

    /* Success Confirmation */
    .success-card {
        background: linear-gradient(135deg, rgba(21, 128, 61, 0.2) 0%, rgba(34, 197, 94, 0.1) 100%);
        border: 1px solid rgba(74, 222, 128, 0.3);
        border-radius: 20px;
        padding: 2.5rem;
        margin: 2rem 0;
        text-align: center;
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px rgba(16, 185, 129, 0.2);
    }

    /* Summary Item Styling */
    .summary-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(20px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    .summary-item {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 14px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
        border: 1px solid rgba(255, 255, 255, 0.05);
        transition: all 0.3s ease;
    }

    .summary-item:hover {
        background: rgba(255, 255, 255, 0.05);
        transform: translateY(-2px);
    }

    .summary-label {
        font-size: 0.85rem;
        color: #94a3b8;
        font-weight: 500;
        margin-bottom: 0.3rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .summary-value {
        font-size: 1.1rem;
        color: #f8fafc;
        font-weight: 600;
    }

    .summary-icon {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
    }

    /* Enhanced Form Styling */
    .stTextInput>div>div>input {
        border-radius: 16px !important;
        border: 2px solid rgba(255, 255, 255, 0.1) !important;
        padding: 1rem 1.5rem !important;
        font-size: 1rem !important;
        background: rgba(255, 255, 255, 0.05) !important;
        color: white !important;
        transition: all 0.3s ease !important;
    }

    .stTextInput>div>div>input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
        background: rgba(255, 255, 255, 0.08) !important;
    }

    .stTextInput>div>div>input::placeholder {
        color: #94a3b8 !important;
    }

    .stButton>button {
        border-radius: 16px !important;
        padding: 1rem 2rem !important;
        font-weight: 600 !important;
        border: none !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        transition: all 0.3s ease !important;
        height: 100% !important;
    }

    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4) !important;
    }

    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}

    /* Enhanced Scrollbar */
    .chat-messages-container::-webkit-scrollbar {
        width: 6px;
    }

    .chat-messages-container::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
    }

    .chat-messages-container::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }

    /* Welcome Message Styling */
    .welcome-message {
        text-align: center;
        padding: 2rem;
        background: rgba(255, 255, 255, 0.03);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin: 1rem 0;
    }

    .welcome-title {
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* Quick Actions in Chat */
    .quick-actions {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin: 1rem 0;
    }

    .quick-action-btn {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #cbd5e1;
        padding: 0.6rem 1rem;
        border-radius: 12px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.3s ease;
        flex: 1;
        min-width: 120px;
        text-align: center;
    }

    .quick-action-btn:hover {
        background: rgba(255, 255, 255, 0.1);
        border-color: rgba(255, 255, 255, 0.2);
        transform: translateY(-2px);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


class BookingApp:
    def __init__(self):
        if 'llm' not in st.session_state:
            st.session_state.llm = OllamaLLM(model="llama3.2", temperature=0)

        if 'agent' not in st.session_state:
            st.session_state.agent = BookingAgent(st.session_state.llm)

    def initialize_session_state(self):
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        if 'slots_visible' not in st.session_state:
            st.session_state.slots_visible = False
        if 'selected_slot' not in st.session_state:
            st.session_state.selected_slot = None
        if 'conversation_active' not in st.session_state:
            st.session_state.conversation_active = True
        if 'last_input' not in st.session_state:
            st.session_state.last_input = ""

    def display_chat_messages(self):
        chat_container = st.container()
        with chat_container:
            # Show welcome message if no messages
            # Display chat messages
            for message in st.session_state.messages:
                content = message.get("content", "")
                if not content or not content.strip():
                    continue
                if message["role"] == "user":
                    st.markdown(f'<div class="user-message">{content}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="assistant-message">{content}</div>', unsafe_allow_html=True)

    def display_time_slots(self):
        agent = st.session_state.agent

        should_show_slots = (
                st.session_state.slots_visible and
                agent.state == 'slots_found' and
                agent.available_slots and
                len(agent.available_slots) > 0 and
                not st.session_state.selected_slot
        )

        if should_show_slots:
            st.markdown("#### 🕒 Available Time Slots")
            st.markdown("Select your preferred appointment time:")

            # Use grid layout for slots
            st.markdown('<div class="slots-grid">', unsafe_allow_html=True)

            cols = st.columns(4)
            for i, slot in enumerate(agent.available_slots[:12]):
                slot_str = f"{slot[0]}-{slot[1]}"
                col_idx = i % 4
                with cols[col_idx]:
                    if st.button(
                            f"🕐 {slot_str}",
                            key=f"slot_{i}",
                            use_container_width=True,
                            type="primary"
                    ):
                        st.session_state.selected_slot = slot_str
                        agent.context['time_str'] = slot_str
                        st.session_state.slots_visible = False

                        st.session_state.messages.append({
                            "role": "user",
                            "content": f"I choose {slot_str}"
                        })
                        response = agent.process_user_input(f"I choose {slot_str}")

                        if response:
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": response
                            })
                        st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

    def show_booking_confirmation(self, slot_str):
        agent = st.session_state.agent

        st.markdown('<div class="success-card">', unsafe_allow_html=True)
        st.markdown("### 🎉 Appointment Confirmed!")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("📅 Date", agent.context.get('date_str', "Not specified"))
        with col2:
            st.metric("🕐 Time", slot_str)
        with col3:
            st.metric("👤 Patient", agent.context.get('patient_str', "Not specified"))

        st.markdown("---")
        st.markdown("📧 **Confirmation email sent** • 📱 **Calendar invite added**")
        st.markdown('</div>', unsafe_allow_html=True)

    def display_status_indicator(self):
        agent = st.session_state.agent

        status_config = {
            'idle': ('💤 Ready to assist', 'status-ready'),
            'awaiting_date': ('📅 Awaiting date selection', 'status-awaiting'),
            'slots_found': ('✅ Time slots available', 'status-active'),
            'completed': ('🎉 Booking complete', 'status-ready')
        }

        status_text, status_class = status_config.get(
            agent.state,
            ('💤 System ready', 'status-ready')
        )

        st.markdown(
            f'<div class="status-pill {status_class}">{status_text}</div>',
            unsafe_allow_html=True
        )

    def display_appointment_summary(self):
        agent = st.session_state.agent

        st.markdown('<div class="summary-card">', unsafe_allow_html=True)
        st.markdown("#### 📋 Appointment Summary")

        summary_items = [
            {"icon": "👤", "label": "PATIENT", "value": agent.context.get('patient_str') or "Not specified"},
            {"icon": "📅", "label": "DATE", "value": agent.context.get('date_str') or "Not selected"},
            {"icon": "🕐", "label": "TIME", "value": st.session_state.selected_slot or "Not selected"},
            {"icon": "📊", "label": "STATUS", "value": agent.state.replace('_', ' ').title()}
        ]

        for item in summary_items:
            st.markdown(
                f"""
                <div class="summary-item">
                    <div class="summary-icon">{item['icon']}</div>
                    <div class="summary-label">{item['label']}</div>
                    <div class="summary-value">{item['value']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown('</div>', unsafe_allow_html=True)

    def process_user_input(self, user_input: str):
        user_input = (user_input or "").strip()
        if not user_input:
            return

        agent = st.session_state.agent
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.spinner("🤔 Processing your request..."):
            response = agent.process_user_input(user_input)
            if response:
                st.session_state.messages.append({"role": "assistant", "content": response})

            if agent.state == 'slots_found' and agent.available_slots and not st.session_state.selected_slot:
                st.session_state.slots_visible = True
            else:
                st.session_state.slots_visible = False

            if agent.state == 'completed':
                time_str = agent.context.get('time_str', st.session_state.selected_slot)
                self.show_booking_confirmation(time_str)

    def render_sidebar(self):
        with st.sidebar:
            st.markdown('<div class="sidebar-content">', unsafe_allow_html=True)

            st.markdown("### 💡 Quick Suggestions")
            st.markdown("Click any suggestion to start:")

            suggestions = [
                "Book an appointment for tomorrow",
                "Show available slots this week",
                "I need an emergency booking",
                "Schedule a follow-up visit",
                "Available times next Monday",
                "Book with Dr. Smith",
                "Cancel my appointment",
                "Reschedule my booking"
            ]

            for i, suggestion in enumerate(suggestions):
                if st.button(suggestion, key=f"sidebar_suggest_{i}", use_container_width=True):
                    self.process_user_input(suggestion)
                    st.rerun()

            st.markdown("---")
            st.markdown("### ⚡ Quick Actions")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("🔄 New Booking", use_container_width=True):
                    agent = st.session_state.agent
                    agent.reset()
                    st.session_state.messages = []
                    st.session_state.slots_visible = False
                    st.session_state.selected_slot = None
                    st.session_state.conversation_active = True
                    st.rerun()

            with col2:
                if st.button("📞 Support", use_container_width=True):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "**Support Information**\n\n📞 +1 (555) 123-4567  \n✉️ support@medibook.com  \n🕒 24/7 Available"
                    })
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

    def render(self):
        self.initialize_session_state()
        agent = st.session_state.agent

        # Header Section
        st.markdown('<div class="main-header">🏥 MediBook Pro</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Premium Healthcare Scheduling Experience</div>', unsafe_allow_html=True)
        if len(st.session_state.messages) == 0:
            st.markdown(
                '''
                <div class="welcome-message">
                    <div class="welcome-title">Welcome to MediBook Pro! 🏥</div>
                    <p>I'm here to help you schedule your healthcare appointments quickly and easily.</p>
                    <div class="quick-actions">
                        <div class="quick-action-btn" onclick="this.style.background='rgba(255,255,255,0.1)'">Book for tomorrow</div>
                        <div class="quick-action-btn" onclick="this.style.background='rgba(255,255,255,0.1)'">Show available slots</div>
                        <div class="quick-action-btn" onclick="this.style.background='rgba(255,255,255,0.1)'">Emergency booking</div>
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        # Main Content Area
        col1, col2 = st.columns([2, 1])

        with col1:
            # Enhanced Chat Container

            col_header1, col_header2 = st.columns([3, 1])
            st.markdown("### 💬 Booking Assistant")
            #st.markdown('<div class="chat-main-container">', unsafe_allow_html=True)
            with col_header1:
                self.display_status_indicator()


            # Chat Messages Area
            st.markdown('<div class="chat-main-container">', unsafe_allow_html=True)
            self.display_chat_messages()

            # Show booking confirmation or time slots
            if agent.state == 'completed' and st.session_state.selected_slot:
                self.show_booking_confirmation(st.session_state.selected_slot)
            else:
                self.display_time_slots()

            st.markdown('</div>', unsafe_allow_html=True)

            # Enhanced Input Area
            if st.session_state.conversation_active and agent.state != 'completed':
                with st.form(key='message_form', clear_on_submit=True):
                    input_cols = st.columns([4, 1])
                    with input_cols[0]:
                        user_text = st.text_input(
                            "💬 Type your message...",
                            placeholder="Hello! I'd like to schedule an appointment...",
                            label_visibility="collapsed",
                            key='form_user_input'
                        )
                    with input_cols[1]:
                        submit = st.form_submit_button('Send →', use_container_width=True)

                    if submit and user_text.strip():
                        self.process_user_input(user_text)
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            # Appointment Summary
            self.display_appointment_summary()

            # Additional info card
            st.markdown('<div class="summary-card">', unsafe_allow_html=True)
            st.markdown("#### ℹ️ Booking Info")
            st.markdown("""
            - **Instant Confirmation**
            - **24/7 Availability**  
            - **HIPAA Compliant**
            - **Email Reminders**
            - **Easy Rescheduling**
            """)
            st.markdown('</div>', unsafe_allow_html=True)

        # Render Sidebar
        self.render_sidebar()

        # Footer
        st.markdown("---")
        st.markdown(
            "<div style='text-align: center; color: #94a3b8; font-size: 0.9rem; padding: 1rem;'>"
            "🔒 HIPAA Compliant • End-to-End Encrypted • MediBook Pro 2024"
            "</div>",
            unsafe_allow_html=True
        )


if __name__ == '__main__':
    app = BookingApp()
    app.render()