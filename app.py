import streamlit as st
import datetime
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

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
        st.rerun()

def update_app_field(app_id, field_name):
    """Updates a specific field (like a note or date) for an application."""
    index = get_app_index(app_id)
    if index is not None:
        widget_key = f"{field_name}_{app_id}"
        new_value = st.session_state[widget_key]
        if isinstance(new_value, str):
            try:
                if ':' in new_value and len(new_value) <= 8:
                    new_value = datetime.time.fromisoformat(new_value)
                elif '-' in new_value:
                    new_value = datetime.date.fromisoformat(new_value)
            except ValueError:
                pass
        st.session_state.applications[index][field_name] = new_value

# --- Data Persistence Functions ---

def load_data(conn):
    """Loads data from Google Sheet and parses dates/times."""
    try:
        df = conn.read(worksheet="Applications", usecols=list(range(11)), ttl=5)
        df = df.dropna(how='all')
        
        # Convert date/time columns from string. GSheets stores everything as strings.
        for col in ['ppt_date', 'test_date']:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        for col in ['ppt_time', 'test_time']:
            df[col] = pd.to_datetime(df[col], format='%H:%M:%S', errors='coerce').dt.time
            
        # --- THIS IS THE FIX ---
        # Explicitly replace all Pandas NaT (Not a Time) values with None.
        # st.date_input/st.time_input cannot handle NaT, they only accept None.
        df = df.astype(object).where(pd.notnull(df), None)
        # --- END OF FIX ---
        
        return df.to_dict('records')
    
    except Exception as e:
        st.error("Failed to load from Google Sheet. See details below.")
        st.exception(e) # This will print the FULL error traceback
        return []

def save_data(conn):
    """Saves the current session state back to Google Sheet."""
    try:
        df = pd.DataFrame(st.session_state.applications)
        for col in ['ppt_date', 'test_date']:
            df[col] = df[col].apply(lambda x: x.isoformat() if isinstance(x, datetime.date) else None)
        for col in ['ppt_time', 'test_time']:
            df[col] = df[col].apply(lambda x: x.isoformat() if isinstance(x, datetime.time) else None)
        
        all_cols = [
            "id", "company", "role", "status", "applied_note", 
            "ppt_note", "ppt_date", "ppt_time", 
            "test_note", "test_date", "test_time"
        ]
        for col in all_cols:
            if col not in df.columns:
                df[col] = None
        df = df[all_cols]

        conn.clear(worksheet="Applications")
        
        # --- THIS IS THE 2nd FIX (Typo correction) ---
        conn.update(worksheet="Applications", data=df) # Was 'works_heet'
        # --- END OF 2nd FIX ---
        
        st.sidebar.success("Saved changes to Google Sheet!")
        
    except Exception as e:
        st.sidebar.error("Failed to save data. See details below.")
        st.exception(e)

# --- State Initialization ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Failed to create Google Sheets connection. Check your [connections.gsheets] in Streamlit Secrets.")
    st.exception(e)
    st.stop()

if 'applications' not in st.session_state:
    st.session_state.applications = load_data(conn)

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
                "id": str(uuid.uuid4()),
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
            st.sidebar.success(f"Added {company} - {role}! Click 'Save' to persist.")
        else:
            st.sidebar.error("Please fill in both Company Name and Role.")

# --- Sidebar: Data Persistence ---
st.sidebar.subheader("Save/Load Data")
st.sidebar.markdown("""
Your data is loaded from Google Sheets. Click **Save** to persist any changes you make.
""")

st.sidebar.button(
    "Save Changes to Cloud", 
    on_click=save_data, 
    args=(conn,), 
    type="primary",
    use_container_width=True
)
st.sidebar.button(
    "Reload from Cloud", 
    on_click=lambda: st.session_state.clear() or st.rerun(),
    use_container_width=True
)

# --- Sidebar: Role Filtering ---
st.sidebar.subheader("Filters")
all_roles = sorted(list(set(app['role'] for app in st.session_state.applications)))

if all_roles:
    selected_roles = st.sidebar.multiselect(
        "Filter by Role",
        options=all_roles,
        default=all_roles
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
    filtered_apps = []

# --- Main Page: Kanban Board ---
col1, col2, col3 = st.columns(3)

# Note: The 'app.get()' method with a default value (e.g., app.get('company', 'N/A'))
# is robust and handles cases where a key might be missing, so we keep that.
# The NaT fix was in load_data, so no changes are needed here.

with col1:
    st.header("Applied 📥")
    for app in filtered_apps:
        if app['status'] == 'Applied':
            if isinstance(app, dict):
                with st.expander(f"**{app.get('company', 'N/A')}** - {app.get('role', 'N/A')}"):
                    st.text_area(
                        "Note", value=app.get('applied_note', ''), key=f"applied_note_{app.get('id')}", 
                        on_change=update_app_field, args=(app.get('id'), 'applied_note')
                    )
                    b_col1, b_col2 = st.columns(2)
                    b_col1.button(
                        "Move to PPT", key=f"move_ppt_{app.get('id')}", 
                        on_click=move_app, args=(app.get('id'), 'PPT'),
                        type="primary", use_container_width=True
                    )
                    b_col2.button(
                        "Delete", key=f"delete_applied_{app.get('id')}", 
                        on_click=delete_app, args=(app.get('id'),),
                        use_container_width=True
                    )
            else:
                st.error(f"Error: Found malformed data in 'Applied' column: {app}")

with col2:
    st.header("PPT 📅")
    for app in filtered_apps:
        if app['status'] == 'PPT':
            if isinstance(app, dict):
                with st.expander(f"**{app.get('company', 'N/A')}** - {app.get('role', 'N/A')}"):
                    st.text_area(
                        "PPT Note", value=app.get('ppt_note', ''), key=f"ppt_note_{app.get('id')}",
                        on_change=update_app_field, args=(app.get('id'), 'ppt_note')
                    )
                    d_col1, d_col2 = st.columns(2)
                    d_col1.date_input(
                        "PPT Date", value=app.get('ppt_date'), key=f"ppt_date_{app.get('id')}",
                        on_change=update_app_field, args=(app.get('id'), 'ppt_date')
                    )
                    d_col2.time_input(
                        "PPT Time", value=app.get('ppt_time'), key=f"ppt_time_{app.get('id')}",
                        on_change=update_app_field, args=(app.get('id'), 'ppt_time')
                    )
                    b_col1, b_col2 = st.columns(2)
                    b_col1.button(
                        "Move to Test", key=f"move_test_{app.get('id')}", 
                        on_click=move_app, args=(app.get('id'), 'Test'),
                        type="primary", use_container_width=True
                    )
                    b_col2.button(
                        "Delete", key=f"delete_ppt_{app.get('id')}", 
                        on_click=delete_app, args=(app.get('id'),),
                        use_container_width=True
                    )
            else:
                st.error(f"Error: Found malformed data in 'PPT' column: {app}")

with col3:
    st.header("Test 📝")
    for app in filtered_apps:
        if app['status'] == 'Test':
            if isinstance(app, dict):
                with st.expander(f"**{app.get('company', 'N/A')}** - {app.get('role', 'N/A')}"):
                    st.text_area(
                        "Test Note", value=app.get('test_note', ''), key=f"test_note_{app.get('id')}",
                        on_change=update_app_field, args=(app.get('id'), 'test_note')
                    )
                    d_col1, d_col2 = st.columns(2)
                    d_col1.date_input(
                        "Test Date", value=app.get('test_date'), key=f"test_date_{app.get('id')}",
                        on_change=update_app_field, args=(app.get('id'), 'test_date')
                    )
                    d_col2.time_input(
                        "Test Time", value=app.get('test_time'), key=f"test_time_{app.get('id')}",
                        on_change=update_app_field, args=(app.get('id'), 'test_time')
                    )
                    st.button(
                        "Delete", key=f"delete_test_{app.get('id')}", 
                        on_click=delete_app, args=(app.get('id'),),
                        use_container_width=True
                    )
            else:
                st.error(f"Error: Found malformed data in 'Test' column: {app}")
