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

# --- Helper Functions (Same as before) ---

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
        widget_key = f"{field_name}_{app_id}"
        new_value = st.session_state[widget_key]
        
        # Handle date/time conversion if necessary (st.time_input can return str)
        if isinstance(new_value, str):
            try:
                if ':' in new_value and len(new_value) <= 8: # Likely a time
                    new_value = datetime.time.fromisoformat(new_value)
                elif '-' in new_value: # Likely a date
                    new_value = datetime.date.fromisoformat(new_value)
            except ValueError:
                pass # Keep as string if parsing fails (e.g., in a note)
                
        st.session_state.applications[index][field_name] = new_value

# --- Data Persistence Functions (NEW) ---

def load_data(conn):
    """Loads data from Google Sheet and parses dates/times."""
    try:
        # Read data from the first sheet (named "Applications")
        df = conn.read(worksheet="Applications", usecols=list(range(11)), ttl=5)
        df = df.dropna(how='all') # Drop empty rows
        
        # Convert date/time columns from string. GSheets stores everything as strings.
        for col in ['ppt_date', 'test_date']:
            # 'coerce' turns bad dates into NaT (Not a Time)
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
        for col in ['ppt_time', 'test_time']:
            # GSheets time format might be tricky, try standard ISO
            df[col] = pd.to_datetime(df[col], format='%H:%M:%S', errors='coerce').dt.time
            
        # Handle NaT/NaN from failed parses, replace with None
        df = df.where(pd.notnull(df), None)
        return df.to_dict('records')
    
    except Exception as e:
        # We add a specific check for the 'Spreadsheet not found' error
        if "SPREADSHEET_NOT_FOUND" in str(e):
            st.error("Error: Spreadsheet not found. Did you set the 'spreadsheet' URL in Streamlit Secrets and share the sheet?")
        else:
            st.error(f"Failed to load from Google Sheet. Did you set it up correctly? Error: {e}")
        return []

def save_data(conn):
    """Saves the current session state back to Google Sheet."""
    try:
        df = pd.DataFrame(st.session_state.applications)
        
        # Convert date/time objects to ISO strings for GSheets
        for col in ['ppt_date', 'test_date']:
            df[col] = df[col].apply(lambda x: x.isoformat() if isinstance(x, datetime.date) else None)
        for col in ['ppt_time', 'test_time']:
            df[col] = df[col].apply(lambda x: x.isoformat() if isinstance(x, datetime.time) else None)
            
        # Ensure all 11 columns exist, even if empty, to match the sheet
        all_cols = [
            "id", "company", "role", "status", "applied_note", 
            "ppt_note", "ppt_date", "ppt_time", 
            "test_note", "test_date", "test_time"
        ]
        for col in all_cols:
            if col not in df.columns:
                df[col] = None
        
        # Reorder columns to match the sheet exactly
        df = df[all_cols]

        # 1. Clear the entire sheet to avoid leaving old data
        conn.clear(worksheet="Applications")
        
        # 2. Update the sheet with the new dataframe
        #    (The headers are written by default)
        conn.update(worksheet="Applications", data=df)
        
        st.sidebar.success("Saved changes to Google Sheet!")
        
    except Exception as e:
        st.sidebar.error(f"Failed to save data: {e}")

# --- State Initialization ---

# Establish GSheets connection
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Failed to create Google Sheets connection. Check your [connections.gsheets] in Streamlit Secrets. Error: {e}")
    st.stop() # Stop the app if connection fails

# Load data from GSheet ONLY on the first run
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
                "id": str(uuid.uuid4()),  # Unique ID
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

# --- Sidebar: Data Persistence (NEW) ---
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

# --- THIS IS THE FIX ---
st.sidebar.button(
    "Reload from Cloud", 
    on_click=lambda: st.session_state.clear() or st.rerun(), # Changed on_clic to on_click
    use_container_width=True
)
# --- END OF FIX ---


# --- Sidebar: Role Filtering (Same as before) ---
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


# --- Main Page: Kanban Board (UPDATED with st.expander) ---
col1, col2, col3 = st.columns(3)

with col1:
    st.header("Applied 📥")
    for app in filtered_apps:
        if app['status'] == 'Applied':
            # Check if app is a dictionary before accessing keys
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
