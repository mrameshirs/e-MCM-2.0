# validation_utils.py
import pandas as pd

MANDATORY_FIELDS_FOR_SHEET = {
    "audit_group_number": "Audit Group Number", "gstin": "GSTIN", "trade_name": "Trade Name", "category": "Category",
    "total_amount_detected_overall_rs": "Total Amount Detected (Overall Rs)",
    "total_amount_recovered_overall_rs": "Total Amount Recovered (Overall Rs)",
    "audit_para_number": "Audit Para Number", "audit_para_heading": "Audit Para Heading",
    "revenue_involved_lakhs_rs": "Revenue Involved (Lakhs Rs)",
    "revenue_recovered_lakhs_rs": "Revenue Recovered (Lakhs Rs)"
}
VALID_CATEGORIES = ["Large", "Medium", "Small"]

def validate_data_for_sheet(data_df_to_validate):
    validation_errors = []
    if data_df_to_validate.empty: return ["No data to validate."]
    for index, row in data_df_to_validate.iterrows():
        row_display_id = f"Row {index + 1} (Para: {row.get('audit_para_number', 'N/A')})"
        for field_key, field_name in MANDATORY_FIELDS_FOR_SHEET.items():
            value = row.get(field_key)
            is_missing = value is None or (isinstance(value, str) and not value.strip()) or pd.isna(value)
            if is_missing:
                if field_key in ["audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
                                 "revenue_recovered_lakhs_rs"] and \
                        row.get('audit_para_heading', "").startswith("N/A - Header Info Only") and pd.isna(
                    row.get('audit_para_number')):
                    continue
                validation_errors.append(f"{row_display_id}: '{field_name}' is missing or empty.")
        category_val = row.get('category')
        if pd.notna(category_val) and category_val.strip() and category_val not in VALID_CATEGORIES:
            validation_errors.append(
                f"{row_display_id}: 'Category' ('{category_val}') is invalid. Must be one of {VALID_CATEGORIES}.")
        elif (pd.isna(category_val) or not str(category_val).strip()) and "category" in MANDATORY_FIELDS_FOR_SHEET:
            validation_errors.append(f"{row_display_id}: 'Category' is missing.")
    if 'trade_name' in data_df_to_validate.columns and 'category' in data_df_to_validate.columns:
        trade_name_categories = {}
        for index, row in data_df_to_validate.iterrows():
            trade_name, category = row.get('trade_name'), row.get('category')
            if pd.notna(trade_name) and str(trade_name).strip() and pd.notna(category) and str(
                    category).strip() and category in VALID_CATEGORIES:
                trade_name_categories.setdefault(trade_name, set()).add(category)
        for tn, cats in trade_name_categories.items():
            if len(cats) > 1: validation_errors.append(
                f"Consistency Error: Trade Name '{tn}' has multiple categories: {', '.join(sorted(list(cats)))}.")
    return sorted(list(set(validation_errors)))