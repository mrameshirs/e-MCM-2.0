# reports_utils.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from dropbox_utils import read_from_spreadsheet
from config import LOG_FILE_PATH

# Expected column names in the log sheet.
LOG_SHEET_COLUMNS = ['Timestamp', 'Username', 'Role']

@st.cache_data(ttl=300)
def get_log_data(_dbx):
    """
    Reads and caches data from the log spreadsheet in Dropbox.
    The _dbx argument is prefixed with an underscore to indicate it's
    used for caching purposes and shouldn't be hashed.
    """
    if not _dbx:
        return pd.DataFrame(columns=LOG_SHEET_COLUMNS)
    
    # Read the log file directly from the defined path in Dropbox
    df = read_from_spreadsheet(_dbx, LOG_FILE_PATH)
    
    # Return an empty DataFrame with correct columns if the sheet is empty or has a different structure
    if df.empty or list(df.columns) != LOG_SHEET_COLUMNS:
         return pd.DataFrame(columns=LOG_SHEET_COLUMNS)
         
    return df

def generate_login_report(df_logs, days):
    """
    Processes the log DataFrame to generate the login activity report.
    (This function requires no changes as it is platform-agnostic)
    """
    if df_logs.empty:
        return pd.DataFrame()

    # Ensure timestamp column is in datetime format
    df_logs['Timestamp'] = pd.to_datetime(df_logs['Timestamp'], errors='coerce')
    df_logs.dropna(subset=['Timestamp'], inplace=True)

    # Filter logs for the selected time period
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered_logs = df_logs[df_logs['Timestamp'] >= cutoff_date]

    if filtered_logs.empty:
        return pd.DataFrame()

    # Count logins and sort the results
    login_counts = filtered_logs.groupby(['Username', 'Role']).size().reset_index(name='Login Count')
    report = login_counts.sort_values(by='Login Count', ascending=False).reset_index(drop=True)
    
    return report
