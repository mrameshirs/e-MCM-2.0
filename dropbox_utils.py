# dropbox_utils.py
import streamlit as st
import dropbox
from datetime import datetime
from dropbox.exceptions import AuthError, ApiError
from io import BytesIO
import pandas as pd
# Import the new config variable
# Import config variables, including LOG_FILE_PATH
from config import (
    DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN, LOG_FILE_PATH
)

def log_activity(dbx, username, role):
    """
    Appends a new login activity record to the log file in Dropbox.
    This function reads the existing file, adds a row, and re-uploads it.
    """
    if not dbx:
        st.warning("Dropbox client is not available. Skipping activity logging.")
        return False

    log_columns = ['Timestamp', 'Username', 'Role']
    
    # Read existing log data from the path specified in config
    df_logs = read_from_spreadsheet(dbx, LOG_FILE_PATH)

    # If the file is empty or has wrong columns, create a new DataFrame in memory
    if df_logs.empty or list(df_logs.columns) != log_columns:
        df_logs = pd.DataFrame(columns=log_columns)

    # Append the new log entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_log_entry = pd.DataFrame([{'Timestamp': timestamp, 'Username': username, 'Role': role}])
    df_logs = pd.concat([df_logs, new_log_entry], ignore_index=True)

    # Upload the updated DataFrame back to Dropbox
    if update_spreadsheet_from_df(dbx, df_logs, LOG_FILE_PATH):
        return True
    else:
        st.error("Failed to update the log file in Dropbox.")
        return False
def get_dropbox_client():
    """Initializes and returns the Dropbox client using a refresh token."""
    try:
        # Check if the secrets have been loaded into the config variables
        if not all([DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN]):
            st.error("Dropbox credentials are not found in Streamlit secrets.")
            return None

        # Initialize the client with the app key, secret, and refresh token
        # The SDK will handle refreshing the access token automatically
        dbx = dropbox.Dropbox(
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET,
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN
        )
        # Test the connection by getting the current user's account info
        dbx.users_get_current_account()
        return dbx
        
    except AuthError as e:
        st.error(f"Authentication Error: Please check your Dropbox credentials. Details: {e}")
        return None
    except Exception as e:
        st.error(f"Failed to connect to Dropbox: {e}")
        return None
        
def get_shareable_link(dbx, dropbox_path):
    """Gets a shareable link for a file, creating one if it doesn't exist."""
    try:
        links = dbx.sharing_list_shared_links(path=dropbox_path, direct_only=True).links
        if links:
            return links[0].url
        else:
            settings = dropbox.sharing.SharedLinkSettings(requested_visibility=dropbox.sharing.RequestedVisibility.public)
            link = dbx.sharing_create_shared_link_with_settings(dropbox_path, settings=settings)
            return link.url
    except ApiError as e:
        # If a link already exists but is not direct_only, this will fail. We can try getting any link.
        try:
            links = dbx.sharing_list_shared_links(path=dropbox_path).links
            if links:
                return links[0].url
        except ApiError:
            pass # Fall through to error if all attempts fail
        print(f"Dropbox API error getting shareable link for {dropbox_path}: {e}")
        return None # Return None if a link can't be fetched or created
        
def upload_file(dbx, file_content, dropbox_path):
    """Uploads a file to a specific path in Dropbox."""
    try:
        dbx.files_upload(file_content, dropbox_path, mode=dropbox.files.WriteMode('overwrite'))
        return True
    except ApiError as e:
        st.error(f"Dropbox API error during upload: {e}")
        return False

def download_file(dbx, dropbox_path):
    """Downloads a file from a specific path in Dropbox."""
    try:
        _, res = dbx.files_download(path=dropbox_path)
        return res.content
    except ApiError as e:
        if isinstance(e.error, dropbox.files.DownloadError) and e.error.is_path() and e.error.get_path().is_not_found():
            return None
        st.error(f"Dropbox API error during download: {e}")
        return None

def read_from_spreadsheet(dbx, dropbox_path):
    """Reads an Excel file in Dropbox into a pandas DataFrame."""
    file_content = download_file(dbx, dropbox_path)
    if file_content:
        try:
            return pd.read_excel(BytesIO(file_content))
        except Exception as e:
            st.error(f"Error reading Excel file from Dropbox: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def update_spreadsheet_from_df(dbx, df_to_write, dropbox_path):
    """Updates an Excel file in Dropbox with data from a pandas DataFrame."""
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_to_write.to_excel(writer, index=False, sheet_name='Sheet1')
        processed_data = output.getvalue()
        return upload_file(dbx, processed_data, dropbox_path)
    except Exception as e:
        st.error(f"Error writing to Excel file for Dropbox upload: {e}")
        return False

def create_folder(dbx, folder_path):
    """Creates a folder in Dropbox if it doesn't already exist."""
    try:
        dbx.files_create_folder_v2(folder_path)
    except ApiError as e:
        if e.error.is_path() and e.error.get_path().is_conflict():
            pass # Folder already exists
        else:
            st.error(f"Dropbox API error during folder creation: {e}")

def list_files(dbx, folder_path):
    """Lists all files in a specific folder in Dropbox."""
    try:
        res = dbx.files_list_folder(folder_path)
        return [entry.name for entry in res.entries]
    except ApiError as e:
        st.error(f"Dropbox API error while listing files: {e}")
        return []# # dropbox_utils.py
# import streamlit as st
# import dropbox
# from dropbox.exceptions import AuthError, ApiError
# from io import BytesIO
# import pandas as pd

# def get_dropbox_client():
#     """Initializes and returns the Dropbox client."""
#     try:
#         dbx_token = st.secrets["dropbox_api_token"]
#         if not dbx_token:
#             st.error("Dropbox API token not found in Streamlit secrets.")
#             return None
#         dbx = dropbox.Dropbox(dbx_token)
#         # Test the connection
#         dbx.users_get_current_account()
#         return dbx
#     except AuthError:
#         st.error("Authentication Error: Invalid Dropbox API token.")
#         return None
#     except Exception as e:
#         st.error(f"Failed to connect to Dropbox: {e}")
#         return None

# def upload_file(dbx, file_content, dropbox_path):
#     """Uploads a file to a specific path in Dropbox."""
#     try:
#         dbx.files_upload(file_content, dropbox_path, mode=dropbox.files.WriteMode('overwrite'))
#         return True
#     except ApiError as e:
#         st.error(f"Dropbox API error during upload: {e}")
#         return False

# def download_file(dbx, dropbox_path):
#     """Downloads a file from a specific path in Dropbox."""
#     try:
#         _, res = dbx.files_download(path=dropbox_path)
#         return res.content
#     except ApiError as e:
#         st.error(f"Dropbox API error during download: {e}")
#         return None

# def read_from_spreadsheet(dbx, dropbox_path):
#     """Reads an entire sheet from an Excel file in Dropbox into a pandas DataFrame."""
#     file_content = download_file(dbx, dropbox_path)
#     if file_content:
#         try:
#             return pd.read_excel(BytesIO(file_content))
#         except Exception as e:
#             st.error(f"Error reading Excel file from Dropbox: {e}")
#             return pd.DataFrame()
#     return pd.DataFrame()

# def update_spreadsheet_from_df(dbx, df_to_write, dropbox_path):
#     """Updates a sheet in an Excel file in Dropbox with data from a pandas DataFrame."""
#     try:
#         output = BytesIO()
#         with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
#             df_to_write.to_excel(writer, index=False, sheet_name='Sheet1')
#         processed_data = output.getvalue()
#         return upload_file(dbx, processed_data, dropbox_path)
#     except Exception as e:
#         st.error(f"Error writing to Excel file for Dropbox upload: {e}")
#         return False

# def create_folder(dbx, folder_path):
#     """Creates a folder in Dropbox if it doesn't already exist."""
#     try:
#         dbx.files_create_folder_v2(folder_path)
#     except ApiError as e:
#         if e.error.is_path() and e.error.get_path().is_conflict():
#             # Folder already exists
#             pass
#         else:
#             st.error(f"Dropbox API error during folder creation: {e}")

# def list_files(dbx, folder_path):
#     """Lists all files in a specific folder in Dropbox."""
#     try:
#         res = dbx.files_list_folder(folder_path)
#         return [entry.name for entry in res.entries]
#     except ApiError as e:
#         st.error(f"Dropbox API error while listing files: {e}")
#         return []
