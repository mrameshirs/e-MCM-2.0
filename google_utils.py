# google_utils.py
import streamlit as st
import os
import json
from io import BytesIO
import pandas as pd

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload

from config import SCOPES, MASTER_DRIVE_FOLDER_NAME, MCM_PERIODS_FILENAME_ON_DRIVE

def get_google_services():
    creds = None
    try:
        creds_dict = st.secrets["google_credentials"]
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=SCOPES
        )
    except KeyError:
        st.error("Google credentials not found in Streamlit secrets. Ensure 'google_credentials' are set.")
        return None, None
    except Exception as e:
        st.error(f"Failed to load service account credentials from secrets: {e}")
        return None, None

    if not creds: return None, None

    try:
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        return drive_service, sheets_service
    except HttpError as error:
        st.error(f"An error occurred initializing Google services: {error}")
        return None, None
    except Exception as e:
        st.error(f"An unexpected error with Google services: {e}")
        return None, None

def find_drive_item_by_name(drive_service, name, mime_type=None, parent_id=None):
    query = f"name = '{name}' and trashed = false"
    if mime_type:
        query += f" and mimeType = '{mime_type}'"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    try:
        response = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = response.get('files', [])
        if items:
            return items[0].get('id')
    except HttpError as error:
        st.warning(f"Error searching for '{name}' in Drive: {error}. This might be okay if the item is to be created.")
    except Exception as e:
        st.warning(f"Unexpected error searching for '{name}' in Drive: {e}")
    return None

def set_public_read_permission(drive_service, file_id):
    try:
        permission = {'type': 'anyone', 'role': 'reader'}
        drive_service.permissions().create(fileId=file_id, body=permission).execute()
    except HttpError as error:
        st.warning(f"Could not set public read permission for file ID {file_id}: {error}.")
    except Exception as e:
        st.warning(f"Unexpected error setting public permission for file ID {file_id}: {e}")

def create_drive_folder(drive_service, folder_name, parent_id=None):
    try:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]

        folder = drive_service.files().create(body=file_metadata, fields='id, webViewLink').execute()
        folder_id = folder.get('id')
        if folder_id:
            set_public_read_permission(drive_service, folder_id)
        return folder_id, folder.get('webViewLink')
    except HttpError as error:
        st.error(f"An error occurred creating Drive folder '{folder_name}': {error}")
        return None, None
    except Exception as e:
        st.error(f"Unexpected error creating Drive folder '{folder_name}': {e}")
        return None, None

def initialize_drive_structure(drive_service):
    master_id = st.session_state.get('master_drive_folder_id')
    if not master_id:
        master_id = find_drive_item_by_name(drive_service, MASTER_DRIVE_FOLDER_NAME,
                                            'application/vnd.google-apps.folder')
        if not master_id:
            st.info(f"Master folder '{MASTER_DRIVE_FOLDER_NAME}' not found on Drive, attempting to create it...")
            master_id, _ = create_drive_folder(drive_service, MASTER_DRIVE_FOLDER_NAME, parent_id=None)
            if master_id:
                st.success(f"Master folder '{MASTER_DRIVE_FOLDER_NAME}' created successfully.")
            else:
                st.error(f"Fatal: Failed to create master folder '{MASTER_DRIVE_FOLDER_NAME}'. Cannot proceed.")
                return False
        st.session_state.master_drive_folder_id = master_id

    if not st.session_state.master_drive_folder_id:
        st.error("Master Drive folder ID could not be established. Cannot proceed.")
        return False

    mcm_file_id = st.session_state.get('mcm_periods_drive_file_id')
    if not mcm_file_id:
        mcm_file_id = find_drive_item_by_name(drive_service, MCM_PERIODS_FILENAME_ON_DRIVE,
                                              parent_id=st.session_state.master_drive_folder_id)
        if mcm_file_id:
            st.session_state.mcm_periods_drive_file_id = mcm_file_id
    return True

def load_mcm_periods(drive_service):
    mcm_periods_file_id = st.session_state.get('mcm_periods_drive_file_id')
    if not mcm_periods_file_id:
        if st.session_state.get('master_drive_folder_id'):
            mcm_periods_file_id = find_drive_item_by_name(drive_service, MCM_PERIODS_FILENAME_ON_DRIVE,
                                                          parent_id=st.session_state.master_drive_folder_id)
            st.session_state.mcm_periods_drive_file_id = mcm_periods_file_id
        else:
            return {}

    if mcm_periods_file_id:
        try:
            request = drive_service.files().get_media(fileId=mcm_periods_file_id)
            fh = BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            return json.load(fh)
        except HttpError as error:
            if error.resp.status == 404:
                st.session_state.mcm_periods_drive_file_id = None
            else:
                st.error(f"Error loading '{MCM_PERIODS_FILENAME_ON_DRIVE}' from Drive: {error}")
            return {}
        except json.JSONDecodeError:
            st.error(f"Error decoding JSON from '{MCM_PERIODS_FILENAME_ON_DRIVE}'. File might be corrupted.")
            return {}
        except Exception as e:
            st.error(f"Unexpected error loading '{MCM_PERIODS_FILENAME_ON_DRIVE}': {e}")
            return {}
    return {}

def save_mcm_periods(drive_service, periods_data):
    master_folder_id = st.session_state.get('master_drive_folder_id')
    if not master_folder_id:
        st.error("Master Drive folder ID not set. Cannot save MCM periods configuration to Drive.")
        return False

    mcm_periods_file_id = st.session_state.get('mcm_periods_drive_file_id')
    file_content = json.dumps(periods_data, indent=4).encode('utf-8')
    fh = BytesIO(file_content)
    media_body = MediaIoBaseUpload(fh, mimetype='application/json', resumable=True)

    try:
        if mcm_periods_file_id:
            file_metadata_update = {'name': MCM_PERIODS_FILENAME_ON_DRIVE}
            drive_service.files().update(
                fileId=mcm_periods_file_id,
                body=file_metadata_update,
                media_body=media_body,
                fields='id, name'
            ).execute()
        else:
            file_metadata_create = {'name': MCM_PERIODS_FILENAME_ON_DRIVE, 'parents': [master_folder_id]}
            new_file = drive_service.files().create(
                body=file_metadata_create,
                media_body=media_body,
                fields='id, name'
            ).execute()
            st.session_state.mcm_periods_drive_file_id = new_file.get('id')
        return True
    except HttpError as error:
        st.error(f"Error saving '{MCM_PERIODS_FILENAME_ON_DRIVE}' to Drive: {error}")
        return False
    except Exception as e:
        st.error(f"Unexpected error saving '{MCM_PERIODS_FILENAME_ON_DRIVE}': {e}")
        return False

def upload_to_drive(drive_service, file_content_or_path, folder_id, filename_on_drive):
    try:
        file_metadata = {'name': filename_on_drive, 'parents': [folder_id]}
        media_body = None

        if isinstance(file_content_or_path, str) and os.path.exists(file_content_or_path):
            media_body = MediaFileUpload(file_content_or_path, mimetype='application/pdf', resumable=True)
        elif isinstance(file_content_or_path, bytes):
            fh = BytesIO(file_content_or_path)
            media_body = MediaIoBaseUpload(fh, mimetype='application/pdf', resumable=True)
        elif isinstance(file_content_or_path, BytesIO):
            file_content_or_path.seek(0)
            media_body = MediaIoBaseUpload(file_content_or_path, mimetype='application/pdf', resumable=True)
        else:
            st.error(f"Unsupported file content type for Google Drive upload: {type(file_content_or_path)}")
            return None, None

        if media_body is None:
            st.error("Media body for upload could not be prepared.")
            return None, None

        request = drive_service.files().create(
            body=file_metadata,
            media_body=media_body,
            fields='id, webViewLink'
        )
        file = request.execute()
        file_id = file.get('id')
        if file_id:
            set_public_read_permission(drive_service, file_id)
        return file_id, file.get('webViewLink')
    except HttpError as error:
        st.error(f"An API error occurred uploading to Drive: {error}")
        return None, None
    except Exception as e:
        st.error(f"An unexpected error in upload_to_drive: {e}")
        return None, None

def create_spreadsheet(sheets_service, drive_service, title, parent_folder_id=None):
    try:
        spreadsheet_body = {'properties': {'title': title}}
        spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet_body,
                                                           fields='spreadsheetId,spreadsheetUrl').execute()
        spreadsheet_id = spreadsheet.get('spreadsheetId')

        if spreadsheet_id and drive_service:
            set_public_read_permission(drive_service, spreadsheet_id)
            if parent_folder_id:
                file = drive_service.files().get(fileId=spreadsheet_id, fields='parents').execute()
                previous_parents = ",".join(file.get('parents'))
                drive_service.files().update(fileId=spreadsheet_id,
                                             addParents=parent_folder_id,
                                             removeParents=previous_parents,
                                             fields='id, parents').execute()
        return spreadsheet_id, spreadsheet.get('spreadsheetUrl')
    except HttpError as error:
        st.error(f"An error occurred creating Spreadsheet: {error}")
        return None, None
    except Exception as e:
        st.error(f"An unexpected error occurred creating Spreadsheet: {e}")
        return None, None

def append_to_spreadsheet(sheets_service, spreadsheet_id, values_to_append):
    try:
        body = {'values': values_to_append}
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', '')
        first_sheet_title = sheets[0].get("properties", {}).get("title", "Sheet1")

        range_to_check = f"{first_sheet_title}!A1:L1"
        result = sheets_service.spreadsheets().values().get(spreadsheetId=spreadsheet_id,
                                                            range=range_to_check).execute()
        header_row_values = result.get('values', [])

        if not header_row_values:
            header_values_list = [[
                "Audit Group Number", "GSTIN", "Trade Name", "Category",
                "Total Amount Detected (Overall Rs)", "Total Amount Recovered (Overall Rs)",
                "Audit Para Number", "Audit Para Heading",
                "Revenue Involved (Lakhs Rs)", "Revenue Recovered (Lakhs Rs)",
                "DAR PDF URL", "Record Created Date"
            ]]
            sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{first_sheet_title}!A1",
                valueInputOption='USER_ENTERED',
                body={'values': header_values_list}
            ).execute()

        append_result = sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{first_sheet_title}!A1",
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        return append_result
    except HttpError as error:
        st.error(f"An error occurred appending to Spreadsheet: {error}")
        return None
    except Exception as e:
        st.error(f"Unexpected error appending to Spreadsheet: {e}")
        return None

def read_from_spreadsheet(sheets_service, spreadsheet_id, sheet_name="Sheet1"):
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_name
        ).execute()
        values = result.get('values', [])
        if not values:
            return pd.DataFrame()
        else:
            expected_cols = [
                "Audit Group Number", "GSTIN", "Trade Name", "Category",
                "Total Amount Detected (Overall Rs)", "Total Amount Recovered (Overall Rs)",
                "Audit Para Number", "Audit Para Heading",
                "Revenue Involved (Lakhs Rs)", "Revenue Recovered (Lakhs Rs)",
                "DAR PDF URL", "Record Created Date"
            ]
            if values and values[0] == expected_cols:
                return pd.DataFrame(values[1:], columns=values[0])
            else:
                if values:
                    if len(values[0]) < len(expected_cols) // 2 or any(isinstance(c, (int, float)) for c in values[0]):
                        return pd.DataFrame(values)
                    else:
                        return pd.DataFrame(values[1:], columns=values[0])
                else:
                    return pd.DataFrame()
    except HttpError as error:
        st.error(f"An error occurred reading from Spreadsheet: {error}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Unexpected error reading from Spreadsheet: {e}")
        return pd.DataFrame()

def delete_spreadsheet_rows(sheets_service, spreadsheet_id, sheet_id_gid, row_indices_to_delete):
    if not row_indices_to_delete:
        return True
    requests = []
    for data_row_index in sorted(row_indices_to_delete, reverse=True):
        sheet_row_start_index = data_row_index + 1
        requests.append({
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id_gid,
                    "dimension": "ROWS",
                    "startIndex": sheet_row_start_index,
                    "endIndex": sheet_row_start_index + 1
                }
            }
        })
    if requests:
        try:
            body = {'requests': requests}
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body=body).execute()
            return True
        except HttpError as error:
            st.error(f"An error occurred deleting rows from Spreadsheet: {error}")
            return False
        except Exception as e:
            st.error(f"Unexpected error deleting rows: {e}")
            return False
    return True