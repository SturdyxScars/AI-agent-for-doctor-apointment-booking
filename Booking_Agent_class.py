from langchain_ollama import OllamaLLM
import json
import re
from date_parse import parse_date, get_current_date
from calendar_functions import construct_calendar_service, find_free_slots_for_date, create_appointment_event
from LLM_prompts import DATE_PARSING_SYSTEM_PROMPT, SLOT_FINDER_PROMPT, BOOKING_DETAILS

calendar_service = construct_calendar_service("client_secret.json")
DEFAULT_CALENDAR_ID = "primary"


class BookingAgent:
    def __init__(self, llm):
        self.llm = llm
        self.state = 'idle'  # idle → awaiting_date → slots_found → booking-details → completed
        self.context = {
            "patient_str": None,
            "date_str": None,
            "time_str": None,
        }
        self.available_slots = []
        self.FUNCTIONS = {
            "parse_date": parse_date,
            "get_current_date": get_current_date,
            "find_free_slots_for_date": find_free_slots_for_date,
            "create_appointment_event": create_appointment_event
        }

    def generate_conversational_response(self, user_input: str, context: str = ""):
        """Generate natural conversational responses without code examples"""
        prompt = f"""
You are a friendly scheduling assistant who schedules appointments for patients with a doctor. Respond naturally to the user's request.

User: {user_input}
{context}

Guidelines:
- Respond conversationally, like a helpful human assistant
- NEVER provide code examples, technical implementations, or programming solutions
- Keep responses concise and friendly
- If you need more information, ask naturally
- Focus on being helpful for scheduling and booking

Your response:"""
        return self.llm.invoke(prompt)

    def extract_json(self, text: str):
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        return json.loads(m.group(0))

    def is_scheduling_request(self, user_input: str) -> bool:
        """Check if the user is asking for scheduling/availability"""
        scheduling_keywords = [
            'available', 'availability', 'slot', 'slots', 'schedule',
            'book', 'appointment', 'meeting', 'time', 'free',
            'check', 'find', 'look for', 'show me'
        ]
        pattern = r'\b(?:' + '|'.join(
            re.escape(k).replace(r'\ ', r'\s+') for k in scheduling_keywords
        ) + r')\b'

        # compile once
        sched_re = re.compile(pattern, flags=re.IGNORECASE)
        return sched_re.search(user_input)

    def parse_time_slots_as_tuples(self, slots_output):
        """
        Parse time slots from the find_free_slots_for_date output

        Args:
            slots_output: Output from find_free_slots_for_date function

        Returns:
            List of tuples with time strings in format ("HH:MM", "HH:MM")
        """
        time_slots = []

        # Extract the list of time slot tuples from the output
        slots_list = slots_output[2]  # Third element contains the list of time slots

        for slot in slots_list:
            start_time, end_time = slot

            # Convert datetime objects to time strings in HH:MM format
            start_str = start_time.strftime("%H:%M")
            end_str = end_time.strftime("%H:%M")

            # Create tuple of time strings
            time_slots.append((start_str, end_str))

        return time_slots

    def process_user_input(self, user_input: str):
        """Main entry point - process user input based on current state"""
        print(f"Current state: {self.state}")

        if self.state == 'idle':
            return self._handle_idle_state(user_input)
        elif self.state == 'awaiting_date':
            return self._handle_awaiting_date_state(user_input)
        elif self.state == 'slots_found':
            return self._handle_slots_found_state(user_input)
        else:
            return "I'm not sure how to process that request."

    def _heuristic_parse_date(self, user_input: str):
        """Try a quick deterministic parse: keywords, common date formats."""
        t = user_input.lower().strip()
        # Quick keywords
        if any(k in t for k in ["tomorrow", "tomoz", "tomorow", "tomoro", "today"]):
            return parse_date("tomorrow", base_date=get_current_date())
        if "day after tomorrow" in t or "day after" in t or "day after tom" in t or "they after tomorrow" in t:
            return parse_date("day after tomorrow", base_date=get_current_date())
        # weekday names
        weekdays = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday","fri","mon","tue","wed","thu","sat","sun"]
        for w in weekdays:
            if re.search(r'\b'+re.escape(w)+r'\b', t):
                return parse_date(w, base_date=get_current_date())
        # numeric date patterns dd/mm, mm/dd, yyyy-mm-dd
        m = re.search(r'(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)', t)
        if m:
            return parse_date(m.group(1), base_date=get_current_date())
        # month name + day
        m = re.search(r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{1,2})', t)
        if m:
            return parse_date(m.group(1), base_date=get_current_date())
        return None


    def _handle_idle_state(self, user_input: str):
        """Handle user input when in idle state"""
        if self.is_scheduling_request(user_input):
            print('DEBUG: appointment related query detected.')

            #extract date immediately from the input phrase
            print("DEBUG: Date phrase detected in initial scheduling request — parsing immediately.")
            self.state = 'awaiting_date'
            # call the awaiting_date handler directly, so it will call parse_date and find slots
            return self._handle_awaiting_date_state(user_input)
        else:
            # Handle non-scheduling requests
            return self._handle_regular_date_request(user_input)

    def _handle_awaiting_date_state(self, user_input: str):
        """Handle user input when waiting for a date"""
        # Parse the date from user input
        prompt = DATE_PARSING_SYSTEM_PROMPT + f"\nUser: {user_input}\nContext: User is providing a date for scheduling an appointment"
        model_reply = self.llm.invoke(prompt)
        print(f"Date Parser raw reply: {model_reply}")

        data = self.extract_json(model_reply)
        if not data:
            return model_reply

        # Direct response
        if "response" in data:
            return data["response"]

        # Function call requested
        if "action" in data:
            action = data["action"]
            fn_name = action["name"]
            if fn_name in self.FUNCTIONS:
                fn = self.FUNCTIONS[fn_name]
                if fn_name == "parse_date":
                    current_date = get_current_date()
                    action['args']['base_date'] = current_date

                result = fn(**action["args"])
                print(f"Parsed date: {result}")

                if result is None:
                    # Still no valid date found
                    return self.generate_conversational_response(
                        user_input,
                        "The user didn't provide a clear date. Gently ask for a specific date or time frame."
                    )
                else:
                    # Valid date found - proceed to find slots
                    self.context['date_str'] = result
                    return self._find_available_slots(user_input, result)

        return "I'm not sure how to process that date."

    def _handle_regular_date_request(self, user_input: str):
        """Handle non-scheduling date-related requests"""
        prompt = DATE_PARSING_SYSTEM_PROMPT + f"\nUser: {user_input}\n"
        model_reply = self.llm.invoke(prompt)
        print(f"Date Parser raw reply: {model_reply}")

        data = self.extract_json(model_reply)
        if not data:
            return model_reply

        # Direct response
        if "response" in data:
            return self.generate_conversational_response(user_input)

        # Function call requested
        if "action" in data:
            action = data["action"]
            fn_name = action["name"]
            if fn_name in self.FUNCTIONS:
                fn = self.FUNCTIONS[fn_name]
                if fn_name == "parse_date":
                    current_date = get_current_date()
                    action['args']['base_date'] = current_date

                result = fn(**action["args"])
                print(f"Parsed date: {result}")

                if result:
                    return self.generate_conversational_response(
                        user_input,
                        f"The user mentioned date {result}. Provide a helpful response."
                    )
                else:
                    return self.generate_conversational_response(user_input)

        return "I'm not sure how to process that request."

    def _find_available_slots(self, user_input: str, parsed_date: str):
        """Find available slots for the given date"""
        prompt = SLOT_FINDER_PROMPT + f"\nUser: {user_input}\nParsed Date: {parsed_date}\n"
        model_reply = self.llm.invoke(prompt)
        print(f"Slot Finder raw reply: {model_reply}")

        data = self.extract_json(model_reply)
        if not data:
            return model_reply

        # Function call requested
        if "action" in data and 'params' in data:
            fn_name = data["action"]
            params = data["params"]
            if fn_name in self.FUNCTIONS:
                fn = self.FUNCTIONS[fn_name]
                if fn_name == "find_free_slots_for_date":
                    # Add required parameters
                    params['service'] = calendar_service
                    params['calendar_id'] = DEFAULT_CALENDAR_ID
                    params['date_str'] = parsed_date

                    result = fn(**params)
                    self.available_slots = self.parse_time_slots_as_tuples(result)
                    print(f"Available slots: {self.available_slots}")

                    # Transition to slots_found state
                    self.state = 'slots_found'

                    # Generate user-friendly response with available slots
                    if self.available_slots:
                        slots_text = ", ".join(
                            [f"{start}-{end}" for start, end in self.available_slots[:8]])  # Show first 8 slots
                        return self.generate_conversational_response(
                            user_input,
                            f"Great! I found available time slots on {parsed_date}: {slots_text}. Which time slot would you prefer?"
                        )
                    else:
                        self.state = 'awaiting_date'  # Go back to ask for different date
                        return self.generate_conversational_response(
                            user_input,
                            f"I'm sorry, but there are no available slots on {parsed_date}. Would you like to try a different date?"
                        )

        return "I'm having trouble finding available slots for that date."

    def _handle_slots_found_state(self, user_input: str):
        """Handle user input when slots have been found"""
        # For now, just acknowledge and reset (you'll extend this later for booking)
        if self.context['time_str']:
            # Time slot is selected, proceed to booking creation
            return self._handle_booking_creation(user_input)
        else:
            # Parse time selection from user input
            # (You might want to add time parsing logic here)
            return self.generate_conversational_response(
                user_input,
                "Please select a time slot from the available options to proceed with booking."
            )

    def _handle_booking_creation(self, user_input: str):
        """Handle the final step of creating the appointment"""
        # REGEX PARSER FOR PROPER NOUN WILL BE REQUIRED. REFER GFG or NLTK .
        print(f"DEBUG: Starting booking creation")
        print(
            f"DEBUG: Context - time_str: {self.context['time_str']}, date_str: {self.context['date_str']}, patient_str: {self.context['patient_str']}")

        if self.context['time_str'] and self.context['date_str']:
            print("DEBUG: Has both time and date")
            # If we already have patient name, create appointment directly
            if self.context['patient_str']:
                print("DEBUG: Has patient name, creating appointment directly")
                try:
                    result = create_appointment_event(
                        service=calendar_service,
                        calendar_id=DEFAULT_CALENDAR_ID,
                        patient_name=self.context['patient_str'],
                        date_str=self.context['date_str'],
                        time_str=self.context['time_str'],
                        description="Appointment booked via MediBook system"
                    )
                    self.state = 'completed'
                    # Store the result before resetting
                    booking_result = f"✅ Appointment successfully booked for {self.context['patient_str']} on {self.context['date_str']} at {self.context['time_str']}!"
                    self.reset()  # Reset after successful booking
                    return booking_result
                except Exception as e:
                    print(f"DEBUG: Exception in direct booking: {e}")
                    return f"❌ Failed to create appointment: {str(e)}"

            else:
                print("DEBUG: No patient name, asking for details")
                # Ask for patient name and description
                prompt = BOOKING_DETAILS + f"\nUser: {user_input}\n"
                model_reply = self.llm.invoke(prompt)
                print(f"DEBUG: LLM reply: {model_reply}")

                data = self.extract_json(model_reply)
                print(f"DEBUG: Extracted JSON: {data}")

                if not data:
                    # If no JSON returned, ask again
                    print("DEBUG: No JSON returned from LLM")
                    return self.generate_conversational_response(
                        user_input,
                        "I need to know the patient's name and reason for visit to complete the booking. Could you please provide both?"
                    )

                # Check if it's the create_appointment_event action
                if "action" in data and data["action"] == "create_appointment_event":
                    args = data.get("args", {})
                    patient_name = args.get("name", "")
                    description = args.get("description", "Appointment booked via MediBook system")
                    print(f"DEBUG: Extracted patient_name: '{patient_name}', description: '{description}'")

                    if patient_name:
                        # Store patient name in context
                        self.context['patient_str'] = patient_name

                        try:
                            print("DEBUG: Attempting to create appointment")
                            # Create the appointment
                            time_to_book = self.context['time_str'].split('-')[0]
                            result = create_appointment_event(
                                service=calendar_service,
                                calendar_id=DEFAULT_CALENDAR_ID,
                                patient_name=patient_name,
                                date_str=self.context['date_str'],
                                time_str=time_to_book,
                                description=description
                            )
                            self.state = 'completed'
                            # Store the result before resetting
                            booking_result = f"✅ Appointment successfully booked for {patient_name} on {self.context['date_str']} at {self.context['time_str']}! Reason: {description}"
                            self.reset()  # Reset after successful booking
                            return booking_result
                        except Exception as e:
                            print(f"DEBUG: Exception in booking with patient name: {e}")
                            return f"❌ Failed to create appointment: {str(e)}"
                    else:
                        print("DEBUG: No patient name extracted from JSON")
                        return self.generate_conversational_response(
                            user_input,
                            "I didn't catch the patient's name. Could you please tell me the name for the booking?"
                        )
                else:
                    # If the LLM didn't return the expected action, ask for info
                    print("DEBUG: LLM didn't return expected action")
                    return self.generate_conversational_response(
                        user_input,
                        "To complete your booking, I need the patient's name. Could you please provide it?"
                    )
        else:
            print(f"DEBUG: Missing time_str: {self.context['time_str']} or date_str: {self.context['date_str']}")
            return "I need both date and time information to create the appointment."# REMOVED: self.reset() from here - it was causing the issue
    def reset(self):
        """Reset the agent to initial state"""
        self.state = 'idle'
        self.context = {
            "patient_str": None,
            "date_str": None,
            "time_str": None,
        }
        self.available_slots = []


# Test the agent properly

# llm = OllamaLLM(model="llama3.2", temperature=0)
# booking_agent = BookingAgent(llm)
#
#
# print(f"Initial State: {booking_agent.state}")
# print(f"Context: {booking_agent.context}")
#
# # Test the booking creation
# while booking_agent.state != 'completed':
#
#     user_input = input("\n")
#     print(f"\nUser: {user_input}")
#     response = booking_agent.process_user_input(user_input)
#     print(f"Assistant: {response}")
#     print(f"Final State: {booking_agent.state}")
