import streamlit as st
import datetime
import json
import uuid

# --- Page Configuration ---
st.set_page_config(
    page_title="Placement Tracker",
    page_icon="📋",
    layout="wide",
)

# --- Helper Functions ---

def get_app_index(app_id):
    """Finds the index of an application in the session state list by its ID."""
    for index, app in enumerate(st.session_state.applications):
        if app['id'] == app_id:
            return index
    return None

def move_app(app_id, new_status):
    """Moves an application to a new status column."""
    index = get_app_index(app_id)
    if index is not None:
        st.session_state.applications[index]['status'] = new_status
        st.success(f"Moved {st.session_state.applications[index]['company']} to {new_status}!")

def delete_app(app_id):
    """Deletes an application from the session state."""
    index = get_app_index(app_id)
    if index is not None:
        company_name = st.session_state.applications[index]['company']
        st.session_state.applications.pop(index)
        st.warning(f"Deleted {company_name} application.")
        st.rerun() # Rerun to update the view immediately

def update_app_field(app_id, field_name):
    """Updates a specific field (like a note or date) for an application."""
    index = get_app_index(app_id)
    if index is not None:
        # The new value is in the session state, under the key of the widget that called this
        widget_key = f"{field_name}_{app_id}"
        new_value = st.session_state[widget_key]
        st.session_state.applications[index][field_name] = new_value

# --- Date/Time JSON Serialization Helpers ---
# These are needed to save/load datetime objects to/from JSON.
def json_converter(o):
    """Converts datetime objects to ISO format strings for JSON."""
    if isinstance(o, (datetime.date, datetime.time)):
        return o.isoformat()

def parse_iso_datetime(data):
    """Converts ISO format strings back to datetime objects after loading from JSON."""
    for app in data:
        for key in ['ppt_date', 'test_date']:
            if app[key]:
                app[key] = datetime.date.fromisoformat(app[key])
        for key in ['ppt_time', 'test_time']:
            if app[key]:
                app[key] = datetime.time.fromisoformat(app[key])
    return data

# --- State Initialization ---
if 'applications' not in st.session_state:
    st.session_state.applications = []

# --- Main Application Title ---
st.title("My Placement Tracker 📋")
st.markdown("Track job applications through your placement season.")

# --- Sidebar ---
st.sidebar.header("Controls")

# --- Sidebar: Add New Application ---
st.sidebar.subheader("Add New Application")
with st.sidebar.form("new_app_form", clear_on_submit=True):
    company = st.text_input("Company Name", key="new_company")
    role = st.text_input("Role", key="new_role")
    applied_note = st.text_area("Initial Note", key="new_note")
    
    submitted = st.form_submit_button("Add Application")
    if submitted:
        if company and role:
            new_app = {
                "id": str(uuid.uuid4()),  # Unique ID for each application
                "company": company,
                "role": role,
                "status": "Applied",
                "applied_note": applied_note,
                "ppt_note": "",
                "ppt_date": None,
                "ppt_time": None,
                "test_note": "",
                "test_date": None,
                "test_time": None,
            }
            st.session_state.applications.append(new_app)
            st.sidebar.success(f"Added {company} - {role}!")
        else:
            st.sidebar.error("Please fill in both Company Name and Role.")

# --- Sidebar: Data Persistence (Save/Load) ---
st.sidebar.subheader("Save/Load Data")
st.sidebar.markdown("""
Since this app runs on a temporary server, you must **download your data** to save it. 
Upload the file back to restore your progress.
""")

# Download data
try:
    json_data = json.dumps(
        st.session_state.applications, 
        default=json_converter, 
        indent=2
    )
    st.sidebar.download_button(
        label="Download Tracker Data (JSON)",
        data=json_data,
        file_name="placement_data.json",
        mime="application/json",
    )
except Exception as e:
    st.sidebar.error(f"Error preparing download: {e}")

# Upload data
uploaded_file = st.sidebar.file_uploader("Upload Tracker Data (JSON)", type=["json"])
if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        # We must parse the string dates back into datetime objects
        st.session_state.applications = parse_iso_datetime(data)
        st.sidebar.success("Data loaded successfully!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error loading file: {e}. Was this a valid JSON from this app?")


# --- Sidebar: Role Filtering ---
st.sidebar.subheader("Filters")
# Get all unique roles from the applications list
all_roles = sorted(list(set(app['role'] for app in st.session_state.applications)))

if all_roles:
    selected_roles = st.sidebar.multiselect(
        "Filter by Role",
        options=all_roles,
        default=all_roles  # By default, show all
    )
else:
    st.sidebar.write("No applications added yet.")
    selected_roles = []

# --- Filter the applications based on sidebar selection ---
if selected_roles:
    filtered_apps = [
        app for app in st.session_state.applications if app['role'] in selected_roles
    ]
else:
    # If no roles are selected (or no apps exist), show nothing
    filtered_apps = [] if all_roles else []


# --- Main Page: Kanban Board ---
col1, col2, col3 = st.columns(3)

with col1:
    st.header("Applied")
    # Iterate over a *copy* to avoid modification issues during iteration
    for app in filtered_apps:
        if app['status'] == 'Applied':
            with st.container(border=True):
                st.subheader(f"{app['company']}")
                st.caption(f"Role: {app['role']}")
                
                # Use 'on_change' to save note edits instantly
                st.text_area(
                    "Note", 
                    value=app['applied_note'], 
                    key=f"applied_note_{app['id']}", 
                    on_change=update_app_field, 
                    args=(app['id'], 'applied_note')
                )
                
                # Use 'on_click' to trigger state-changing functions
                st.button(
                    "Move to PPT", 
                    key=f"move_ppt_{app['id']}", 
                    on_click=move_app, 
                    args=(app['id'], 'PPT'),
                    type="primary"
                )
                st.button(
                    "Delete", 
                    key=f"delete_applied_{app['id']}", 
                    on_click=delete_app, 
                    args=(app['id'],)
                )

with col2:
    st.header("PPT")
    for app in filtered_apps:
        if app['status'] == 'PPT':
            with st.container(border=True):
                st.subheader(f"{app['company']}")
                st.caption(f"Role: {app['role']}")

                st.text_area(
                    "PPT Note", 
                    value=app['ppt_note'], 
                    key=f"ppt_note_{app['id']}",
                    on_change=update_app_field, 
                    args=(app['id'], 'ppt_note')
                )
                st.date_input(
                    "PPT Date", 
                    value=app['ppt_date'], 
                    key=f"ppt_date_{app['id']}",
                    on_change=update_app_field, 
                    args=(app['id'], 'ppt_date')
                )
                st.time_input(
                    "PPT Time", 
                    value=app['ppt_time'], 
                    key=f"ppt_time_{app['id']}",
                    on_change=update_app_field, 
                    args=(app['id'], 'ppt_time')
                )
                
                st.button(
                    "Move to Test", 
                    key=f"move_test_{app['id']}", 
                    on_click=move_app, 
                    args=(app['id'], 'Test'),
                    type="primary"
                )
                st.button(
                    "Delete", 
                    key=f"delete_ppt_{app['id']}", 
                    on_click=delete_app, 
                    args=(app['id'],)
                )

with col3:
    st.header("Test")
    for app in filtered_apps:
        if app['status'] == 'Test':
            with st.container(border=True):
                st.subheader(f"{app['company']}")
                st.caption(f"Role: {app['role']}")
                
                st.text_area(
                    "Test Note", 
                    value=app['test_note'], 
                    key=f"test_note_{app['id']}",
                    on_change=update_app_field, 
                    args=(app['id'], 'test_note')
                )
                st.date_input(
                    "Test Date", 
                    value=app['test_date'], 
                    key=f"test_date_{app['id']}",
                    on_change=update_app_field, 
                    args=(app['id'], 'test_date')
                )
                st.time_input(
                    "Test Time", 
                    value=app['test_time'], 
                    key=f"test_time_{app['id']}",
                    on_change=update_app_field, 
                    args=(app['id'], 'test_time')
                )
                
                st.button(
                    "Delete", 
                    key=f"delete_test_{app['id']}", 
                    on_click=delete_app, 
                    args=(app['id'],)
                )
