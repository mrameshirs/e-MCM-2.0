# validation_utils.py
import pandas as pd
from config import GST_RISK_PARAMETERS, TAXPAYER_CLASSIFICATION_OPTIONS

MANDATORY_FIELDS_FOR_SHEET = {
    "audit_group_number": "Audit Group Number",
    "gstin": "GSTIN",
    "trade_name": "Trade Name",
    "category": "Category",
    "taxpayer_classification": "Taxpayer Classification",
    "total_amount_detected_overall_rs": "Total Amount Detected (Overall Rs)",
    "total_amount_recovered_overall_rs": "Total Amount Recovered (Overall Rs)",
    "audit_para_number": "Audit Para Number",
    "audit_para_heading": "Audit Para Heading",
    "revenue_involved_rs": "Revenue Involved (Rs)",
    "revenue_recovered_rs": "Revenue Recovered (Rs)",
    "status_of_para": "Status of para"
}
VALID_CATEGORIES = ["Large", "Medium", "Small"]
VALID_PARA_STATUSES = [
    'Agreed and Paid', 'Agreed yet to pay',
    'Partially agreed and paid', 'Partially agreed, yet to pay',
    'Not agreed'
]

def validate_data_for_sheet(data_df_to_validate, risk_data, no_risk_flags_checked):
    validation_errors = []
    if data_df_to_validate.empty:
        return ["No data to validate."]

    # --- Risk Flag Validation ---
    if not no_risk_flags_checked:
        if not risk_data:
            validation_errors.append("Risk Flags Error: At least one risk flag must be specified, or the 'No risk flags' checkbox must be ticked.")
        else:
            all_valid_para_numbers = data_df_to_validate['audit_para_number'].dropna().unique().tolist()
            for item in risk_data:
                flag = item.get('risk_flag')
                paras = item.get('paras', [])
                if not flag or flag not in GST_RISK_PARAMETERS:
                    validation_errors.append(f"Risk Flags Error: Invalid risk flag code '{flag}' found.")
                
                # --- REMOVED VALIDATION ---
                # This rule is no longer enforced, allowing risk flags to exist without linked paras.
                # if not paras:
                #     validation_errors.append(f"Risk Flags Error: Risk flag '{flag}' must be linked to at least one audit para number.")
                
                # This rule remains: if a para is linked, it must be a valid para number from the table
                for para_num in paras:
                    if para_num not in all_valid_para_numbers:
                        validation_errors.append(f"Risk Flags Error: Para number '{para_num}' linked to risk flag '{flag}' does not exist in the main table.")

    for index, row in data_df_to_validate.iterrows():
        row_display_id = f"Row {index + 1} (Para: {row.get('audit_para_number', 'N/A')})"

        # Check mandatory fields
        for field_key, field_name in MANDATORY_FIELDS_FOR_SHEET.items():
            value = row.get(field_key)
            is_missing = value is None or (isinstance(value, str) and not value.strip()) or pd.isna(value)

            if is_missing:
                if field_key in ["audit_para_number", "audit_para_heading",
                                 "revenue_involved_rs", "revenue_recovered_rs",
                                 "status_of_para"] and \
                   row.get('audit_para_heading', "").startswith("N/A - Header Info Only") and \
                   pd.isna(row.get('audit_para_number')):
                    continue
                validation_errors.append(f"{row_display_id}: '{field_name}' is missing or empty.")

        # Validate 'category'
        category_val = row.get('category')
        if pd.notna(category_val) and str(category_val).strip() and str(category_val) not in VALID_CATEGORIES:
            validation_errors.append(f"{row_display_id}: 'Category' ('{category_val}') is invalid. Must be one of {VALID_CATEGORIES}.")

        # Validate 'taxpayer_classification'
        tax_class_val = row.get('taxpayer_classification')
        if pd.notna(tax_class_val) and str(tax_class_val).strip() and str(tax_class_val) not in TAXPAYER_CLASSIFICATION_OPTIONS:
            validation_errors.append(f"{row_display_id}: 'Taxpayer Classification' ('{tax_class_val}') is invalid.")

        # Validate 'status_of_para'
        status_val = row.get('status_of_para')
        is_header_only_row_for_status = row.get('audit_para_heading', "").startswith("N/A - Header Info Only") and pd.isna(row.get('audit_para_number'))

        if not is_header_only_row_for_status:
            if pd.notna(status_val) and str(status_val).strip() and str(status_val) not in VALID_PARA_STATUSES:
                validation_errors.append(f"{row_display_id}: 'Status of para' ('{status_val}') is invalid. Must be one of {VALID_PARA_STATUSES}.")
            elif (pd.isna(status_val) or not str(status_val).strip()) and "status_of_para" in MANDATORY_FIELDS_FOR_SHEET:
                 validation_errors.append(f"{row_display_id}: 'Status of para' is missing for a data para.")

    # Consistency check for header-level fields per 'trade_name'
    if 'trade_name' in data_df_to_validate.columns:
        consistency_fields = ['category', 'taxpayer_classification']
        for field in consistency_fields:
            if field in data_df_to_validate.columns:
                trade_name_groups = {}
                for index, row in data_df_to_validate.iterrows():
                    trade_name, value = row.get('trade_name'), row.get(field)
                    if pd.notna(trade_name) and str(trade_name).strip() and pd.notna(value) and str(value).strip():
                        trade_name_groups.setdefault(trade_name, set()).add(value)

                for tn, vals in trade_name_groups.items():
                    if len(vals) > 1:
                        validation_errors.append(f"Consistency Error: Trade Name '{tn}' has multiple values for '{field.replace('_', ' ').title()}': {', '.join(sorted(list(vals)))}.")

    return sorted(list(set(validation_errors)))
    # # validation_utils.py
# import pandas as pd
# from config import GST_RISK_PARAMETERS, TAXPAYER_CLASSIFICATION_OPTIONS

# MANDATORY_FIELDS_FOR_SHEET = {
#     "audit_group_number": "Audit Group Number",
#     "gstin": "GSTIN",
#     "trade_name": "Trade Name",
#     "category": "Category",
#     "taxpayer_classification": "Taxpayer Classification", # New mandatory field
#     "total_amount_detected_overall_rs": "Total Amount Detected (Overall Rs)",
#     "total_amount_recovered_overall_rs": "Total Amount Recovered (Overall Rs)",
#     "audit_para_number": "Audit Para Number",
#     "audit_para_heading": "Audit Para Heading",
#     "revenue_involved_rs": "Revenue Involved (Rs)",
#     "revenue_recovered_rs": "Revenue Recovered (Rs)",
#     "status_of_para": "Status of para"
# }
# VALID_CATEGORIES = ["Large", "Medium", "Small"]
# VALID_PARA_STATUSES = [
#     'Agreed and Paid', 'Agreed yet to pay',
#     'Partially agreed and paid', 'Partially agreed, yet to pay',
#     'Not agreed'
# ]

# def validate_data_for_sheet(data_df_to_validate, risk_data, no_risk_flags_checked):
#     validation_errors = []
#     if data_df_to_validate.empty:
#         return ["No data to validate."]

#     # --- Risk Flag Validation ---
#     if not no_risk_flags_checked:
#         if not risk_data:
#             validation_errors.append("Risk Flags Error: At least one risk flag must be specified, or the 'No risk flags' checkbox must be ticked.")
#         else:
#             all_valid_para_numbers = data_df_to_validate['audit_para_number'].dropna().unique().tolist()
#             for item in risk_data:
#                 flag = item.get('risk_flag')
#                 paras = item.get('paras', [])
#                 if not flag or flag not in GST_RISK_PARAMETERS:
#                     validation_errors.append(f"Risk Flags Error: Invalid risk flag code '{flag}' found.")
#                 if not paras:
#                     validation_errors.append(f"Risk Flags Error: Risk flag '{flag}' must be linked to at least one audit para number.")
#                 for para_num in paras:
#                     if para_num not in all_valid_para_numbers:
#                         validation_errors.append(f"Risk Flags Error: Para number '{para_num}' linked to risk flag '{flag}' does not exist in the main table.")

#     for index, row in data_df_to_validate.iterrows():
#         row_display_id = f"Row {index + 1} (Para: {row.get('audit_para_number', 'N/A')})"

#         # Check mandatory fields
#         for field_key, field_name in MANDATORY_FIELDS_FOR_SHEET.items():
#             value = row.get(field_key)
#             is_missing = value is None or (isinstance(value, str) and not value.strip()) or pd.isna(value)

#             if is_missing:
#                 if field_key in ["audit_para_number", "audit_para_heading",
#                                  "revenue_involved_rs", "revenue_recovered_rs",
#                                  "status_of_para"] and \
#                    row.get('audit_para_heading', "").startswith("N/A - Header Info Only") and \
#                    pd.isna(row.get('audit_para_number')):
#                     continue
#                 validation_errors.append(f"{row_display_id}: '{field_name}' is missing or empty.")

#         # Validate 'category'
#         category_val = row.get('category')
#         if pd.notna(category_val) and str(category_val).strip() and str(category_val) not in VALID_CATEGORIES:
#             validation_errors.append(f"{row_display_id}: 'Category' ('{category_val}') is invalid. Must be one of {VALID_CATEGORIES}.")

#         # Validate 'taxpayer_classification'
#         tax_class_val = row.get('taxpayer_classification')
#         if pd.notna(tax_class_val) and str(tax_class_val).strip() and str(tax_class_val) not in TAXPAYER_CLASSIFICATION_OPTIONS:
#             validation_errors.append(f"{row_display_id}: 'Taxpayer Classification' ('{tax_class_val}') is invalid.")

#         # Validate 'status_of_para'
#         status_val = row.get('status_of_para')
#         is_header_only_row_for_status = row.get('audit_para_heading', "").startswith("N/A - Header Info Only") and pd.isna(row.get('audit_para_number'))

#         if not is_header_only_row_for_status:
#             if pd.notna(status_val) and str(status_val).strip() and str(status_val) not in VALID_PARA_STATUSES:
#                 validation_errors.append(f"{row_display_id}: 'Status of para' ('{status_val}') is invalid. Must be one of {VALID_PARA_STATUSES}.")
#             elif (pd.isna(status_val) or not str(status_val).strip()) and "status_of_para" in MANDATORY_FIELDS_FOR_SHEET:
#                  validation_errors.append(f"{row_display_id}: 'Status of para' is missing for a data para.")

#     # Consistency check for header-level fields per 'trade_name'
#     if 'trade_name' in data_df_to_validate.columns:
#         consistency_fields = ['category', 'taxpayer_classification']
#         for field in consistency_fields:
#             if field in data_df_to_validate.columns:
#                 trade_name_groups = {}
#                 for index, row in data_df_to_validate.iterrows():
#                     trade_name, value = row.get('trade_name'), row.get(field)
#                     if pd.notna(trade_name) and str(trade_name).strip() and pd.notna(value) and str(value).strip():
#                         trade_name_groups.setdefault(trade_name, set()).add(value)

#                 for tn, vals in trade_name_groups.items():
#                     if len(vals) > 1:
#                         validation_errors.append(f"Consistency Error: Trade Name '{tn}' has multiple values for '{field.replace('_', ' ').title()}': {', '.join(sorted(list(vals)))}.")

#     return sorted(list(set(validation_errors)))
#     # # validation_utils.py
# # import pandas as pd

# # MANDATORY_FIELDS_FOR_SHEET = {
# #     "audit_group_number": "Audit Group Number",
# #     # "audit_circle_number": "Audit Circle Number", # This will be derived, not from extraction
# #     "gstin": "GSTIN",
# #     "trade_name": "Trade Name",
# #     "category": "Category",
# #     "total_amount_detected_overall_rs": "Total Amount Detected (Overall Rs)",
# #     "total_amount_recovered_overall_rs": "Total Amount Recovered (Overall Rs)",
# #     "audit_para_number": "Audit Para Number",
# #     "audit_para_heading": "Audit Para Heading",
# #     "revenue_involved_lakhs_rs": "Revenue Involved (Lakhs Rs)",
# #     "revenue_recovered_lakhs_rs": "Revenue Recovered (Lakhs Rs)",
# #     "status_of_para": "Status of para" # New mandatory field
# # }
# # VALID_CATEGORIES = ["Large", "Medium", "Small"]
# # VALID_PARA_STATUSES = [
# #     'Agreed and Paid', 'Agreed yet to pay',
# #     'Partially agreed and paid', 'Partially agreed, yet to paid', # Corrected typo from "yet to paid" to "yet to pay"
# #     'Not agreed'
# # ]

# # def validate_data_for_sheet(data_df_to_validate):
# #     validation_errors = []
# #     if data_df_to_validate.empty:
# #         return ["No data to validate."]

# #     for index, row in data_df_to_validate.iterrows():
# #         row_display_id = f"Row {index + 1} (Para: {row.get('audit_para_number', 'N/A')})"

# #         # Check mandatory fields
# #         for field_key, field_name in MANDATORY_FIELDS_FOR_SHEET.items():
# #             value = row.get(field_key) # Use field_key which matches DataFrame columns from Pydantic model
# #             is_missing = value is None or (isinstance(value, str) and not value.strip()) or pd.isna(value)

# #             if is_missing:
# #                 # Special handling for para-specific fields if it's a header-only row
# #                 if field_key in ["audit_para_number", "audit_para_heading",
# #                                  "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs",
# #                                  "status_of_para"] and \
# #                    row.get('audit_para_heading', "").startswith("N/A - Header Info Only") and \
# #                    pd.isna(row.get('audit_para_number')):
# #                     continue # Skip validation for these fields in a header-only row
# #                 validation_errors.append(f"{row_display_id}: '{field_name}' is missing or empty.")

# #         # Validate 'category'
# #         category_val = row.get('category')
# #         if pd.notna(category_val) and str(category_val).strip() and str(category_val) not in VALID_CATEGORIES:
# #             validation_errors.append(
# #                 f"{row_display_id}: 'Category' ('{category_val}') is invalid. Must be one of {VALID_CATEGORIES}.")
# #         # Mandatory check for category is covered by the loop above if 'category' is in MANDATORY_FIELDS_FOR_SHEET

# #         # Validate 'status_of_para'
# #         status_val = row.get('status_of_para')
# #         # Allow status to be missing for header-only rows
# #         is_header_only_row_for_status = row.get('audit_para_heading', "").startswith("N/A - Header Info Only") and pd.isna(row.get('audit_para_number'))

# #         if not is_header_only_row_for_status: # Only validate status for actual para rows
# #             if pd.notna(status_val) and str(status_val).strip() and str(status_val) not in VALID_PARA_STATUSES:
# #                 validation_errors.append(
# #                     f"{row_display_id}: 'Status of para' ('{status_val}') is invalid. Must be one of {VALID_PARA_STATUSES}.")
# #             elif (pd.isna(status_val) or not str(status_val).strip()) and "status_of_para" in MANDATORY_FIELDS_FOR_SHEET:
# #                  validation_errors.append(f"{row_display_id}: 'Status of para' is missing for a data para.")


# #     # Consistency check for 'category' per 'trade_name'
# #     if 'trade_name' in data_df_to_validate.columns and 'category' in data_df_to_validate.columns:
# #         trade_name_categories = {}
# #         for index, row in data_df_to_validate.iterrows():
# #             trade_name, category = row.get('trade_name'), row.get('category')
# #             if pd.notna(trade_name) and str(trade_name).strip() and \
# #                pd.notna(category) and str(category).strip() and category in VALID_CATEGORIES:
# #                 trade_name_categories.setdefault(trade_name, set()).add(category)

# #         for tn, cats in trade_name_categories.items():
# #             if len(cats) > 1:
# #                 validation_errors.append(
# #                     f"Consistency Error: Trade Name '{tn}' has multiple categories: {', '.join(sorted(list(cats)))}.")

# #     return sorted(list(set(validation_errors)))# # validation_utils.py
