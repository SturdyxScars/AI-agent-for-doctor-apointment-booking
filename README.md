# **Conversational Medical Appointment Agent**

A fully local conversational agent that finds available calendar slots and books medical appointments using:

* **Ollama** (running locally) with **Llama 3.2**
* **Google Calendar API**
* **Python (LangChain + custom rule-based logic)**

This project runs **entirely on your machine**. No cloud LLMs required.

---

## **🔧 Features**

* Natural language conversation for scheduling.
* Local Llama 3.2 model via Ollama → fast, private inference.
* Automatically:

  * Detects user intent.
  * Extracts dates, times, names.
  * Searches Google Calendar for available slots.
  * Books appointments with confirmation.
* Robust rule-based fallback → avoids LLM hallucinations.
* Debug-friendly (prints LLM output + exceptions for calendar logic).

---

# **🖥️ Run Locally (Step-by-Step)**

## **1. Clone the Repository**

```bash
git clone https://github.com/<your-username>/<project-name>.git
cd <project-name>
```

---

## **2. Install Python & Create Virtual Environment**

```bash
python -m venv .venv
source .venv/bin/activate     # macOS / Linux
.venv\Scripts\activate        # Windows
```

---

## **3. Install Dependencies**

```bash
pip install -r requirements.txt
```

If any of these are missing, install manually:

```bash
pip install langchain-ollama google-api-python-client \
            google-auth-httplib2 google-auth-oauthlib python-dotenv
```

---

# **4. Install & Run Ollama**

### **Install Ollama**

Follow the official instructions:
[https://ollama.com/download](https://ollama.com/download)

### **Pull the Llama3.2 Model**

```bash
ollama pull llama3.2
```

### **Start Ollama Server**

(Usually starts automatically)

```bash
ollama serve
```

Verify it's running:

```bash
curl http://localhost:11434/v1/models
```

---

# **5. Configure Google Calendar API**

### **How to set it up:**

1. Go to: [https://console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)
2. Create **OAuth Client ID** (Desktop App) or **Service Account**.
3. Enable the **Google Calendar API**.
4. Download the credential file.
5. Save it as:

```
./LLM_agent/client_secret.json
```

> **Important:**
> Your calendar must be accessible using that credential (shared or owned).

---

# **6. Run the Agent**

The main script includes a simulation test.
To run it:

```bash
python conversational_agent_patched.py
```

You’ll see a test conversation:

```
Hello!
I want to find free slots for 2025-11-25
...
```

To use it interactively, import it in a Python REPL:

```python
from conversational_agent_patched import conversational_run_agent

ctx = {"pending_action": None, "args": {}, "history": [], "available_slots": []}

reply, ctx = conversational_run_agent("Find available slots for 2025-11-25", ctx)
print(reply)
```

Pass the **same `ctx`** into each call to maintain conversation memory.

---

# **7. Optional: Run with Streamlit (Locally Only)**

Create file `app.py`:

```python
import streamlit as st
from conversational_agent_patched import conversational_run_agent

st.title("Local Appointment Agent (Ollama + Google Calendar)")

if "ctx" not in st.session_state:
    st.session_state.ctx = {"pending_action": None, "args": {}, "history": [], "available_slots": []}

user_input = st.text_input("You:")
if st.button("Send"):
    reply, ctx = conversational_run_agent(user_input, st.session_state.ctx)
    st.session_state.ctx = ctx
    st.write(reply)
```

Run:

```bash
streamlit run app.py
```

> **Note:** Streamlit Cloud cannot access your local Ollama.
> So Streamlit UI is **local only**, unless you host Ollama on a remote machine.

---

# **📂 Project Structure**

```
📁 project/
│
├── conversational_agent.py        # Main conversational agent (LLM + rules + calendar logic)
├── calendar_functions.py          # Calendar helper utilities (find slot logic, booking helpers)
├── google_apis.py                 # Google Calendar API service construction + auth handling
├── stream_run.py                  # Optional Streamlit UI to run the agent locally
│
├── requirements.txt               # Python dependencies
├── client_secret.json             # Google API OAuth/Service Account credentials (DO NOT COMMIT)
│
└── README.md

```

---

# **🔐 Security Notes**

* Never commit `client_secret.json`.
* Never expose local Ollama to the internet without protection.
* Keep `.env` and credentials out of the repo.

---

# **❗Troubleshooting**

### **1. Error: “Cannot attend all appointments”**

This comes from Google Calendar. Check:

* Calendar permissions
* Date/time format
* Timezone settings
* Whether working hours block everything
* Conflicts with existing events

---

# **✔️ This project is designed for local-first AI**

Perfect for:

* private scheduling systems
* offline assistants
* experimenting with LLM reasoning + rule-based logic
* building medical/clinic automation prototypes

---
[! watch video]
(https://drive.google.com/file/d/1z4FXDycZGvc37e1r4xk8lhGgqlllTN0i/view?usp=sharing)
