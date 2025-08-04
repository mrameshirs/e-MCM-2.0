# # config.py
import streamlit as st

# --- Dropbox Configuration ---
DROPBOX_APP_KEY = st.secrets.get("dropbox_app_key", "")
DROPBOX_APP_SECRET = st.secrets.get("dropbox_app_secret", "")
#DROPBOX_API_TOKEN = st.secrets.get("dropbox_api_token", "")
# NEW: Use the refresh token
DROPBOX_REFRESH_TOKEN = st.secrets.get("dropbox_refresh_token", "")
# --- Centralized Folders and Files ---
DROPBOX_ROOT_PATH = "/e-MCM_App"
DAR_PDFS_PATH = f"{DROPBOX_ROOT_PATH}/DAR_PDFs"
OFFICE_ORDERS_PATH = f"{DROPBOX_ROOT_PATH}/Office_Orders" # Path for allocation/reallocation orders
MCM_DATA_PATH = f"{DROPBOX_ROOT_PATH}/mcm_dar_data.xlsx"
LOG_SHEET_PATH = f"{DROPBOX_ROOT_PATH}/log_sheet.xlsx"
LOG_FILE_PATH = f"{DROPBOX_ROOT_PATH}/log_sheet.xlsx"
SMART_AUDIT_DATA_PATH = f"{DROPBOX_ROOT_PATH}/smart_audit_data.xlsx"
MCM_PERIODS_INFO_PATH = f"{DROPBOX_ROOT_PATH}/mcm_periods_info.xlsx"


# --- User Credentials ---
USER_CREDENTIALS = {
    "planning_officer": "pco_password",
    **{f"audit_group{i}": f"ag{i}_audit" for i in range(1, 31)}
}
USER_ROLES = {
    "planning_officer": "PCO",
    **{f"audit_group{i}": "AuditGroup" for i in range(1, 31)}
}
AUDIT_GROUP_NUMBERS = {
    f"audit_group{i}": i for i in range(1, 31)
}
# --- New Constants for DAR Data Enhancement ---

TAXPAYER_CLASSIFICATION_OPTIONS = [
    "Trader – Jewellery & precious stones",
    "Trader- Iron and steels",
    "Other Traders",
    "Manufacturer",
    "Service Sector- Construction",
    "Service Sector- (BFSI) Banks, Financial services, Insurance",
    "Service sector -Tours ,Travels ,Logistics",
    "Service sector-IT and Consultancy",
    "Other service sectors"
]

GST_RISK_PARAMETERS = {
    "P01": "Sale turnover (GSTR-3B) is less than the purchase turnover",
    "P03": "High ratio of nil-rated/exempt supplies to total turnover",
    "P04": "High ratio of zero-rated supplies to total turnover",
    "P09": "Decline in average monthly taxable turnover in GSTR-3B",
    "P10": "High ratio of non-GST supplies to total turnover",
    "P21": "High ratio of zero-rated supply to SEZ to total GST turnover",
    "P22": "High ratio of deemed exports to total GST turnover",
    "P23": "High ratio of zero-rated supply (other than exports) to total supplies",
    "P29": "High ratio of taxable turnover as per ITC-04 vs. total turnover in GSTR-3B",
    "P31": "High ratio of Credit Notes to total taxable turnover value",
    "P32": "High ratio of Debit Notes to total taxable turnover value",
    "P02": "IGST paid on import is more than the ITC availed in GSTR-3B",
    "P05": "High ratio of inward supplies liable to reverse charge to total turnover",
    "P06": "Mismatch between RCM liability declared and ITC claimed on RCM",
    "P07": "High ratio of tax paid through ITC to total tax payable",
    "P14": "Positive difference between ITC availed in GSTR-3B and ITC available in GSTR-2A",
    "P15": "Positive difference between ITC on import of goods (GSTR-3B) and IGST paid at Customs",
    "P16": "Low ratio of tax paid under RCM compared to ITC claimed on RCM",
    "P17": "High ratio of ISD credit to total ITC availed",
    "P18": "Low ratio of ITC reversed to total ITC availed",
    "P19": "Mismatch between the proportion of exempt supplies and the proportion of ITC reversed",
    "P08": "Low ratio of tax payment in cash to total tax liability",
    "P11": "Taxpayer has filed more than six GST returns late",
    "P12": "Taxpayer has not filed three consecutive GSTR-3B returns",
    "P30": "Taxpayer was selected for audit on risk criteria last year but was not audited",
    "P13": "Taxpayer has both SEZ and non-SEZ registrations with the same PAN in the same state",
    "P20": "Mismatch between the taxable value of exports in GSTR-1 and the IGST value in shipping bills (Customs data)",
    "P24": "Risk associated with other linked GSTINs of the same PAN",
    "P28": "Taxpayer is flagged in Red Flag Reports of DGARM",
    "P33": "Substantial difference between turnover in GSTR-3B and turnover in Income Tax Return (ITR)",
    "P34": "Negligible income tax payment despite substantial turnover in GSTR-3B",
    "P25": "High amount of IGST Refund claimed (for Risky Exporters)",
    "P26": "High amount of LUT Export Refund claimed (for Risky Exporters)",
    "P27": "High amount of Refund claimed due to inverted duty structure (for Risky Exporters)"
}

RISK_PARAMETER_GROUPS = {
    "GROUP A - TURNOVER & SUPPLY PATTERN": ["P01", "P03", "P04", "P09", "P10", "P21", "P22", "P23", "P29", "P31", "P32"],
    "GROUP B - INPUT TAX CREDIT & INWARD SUPPLY": ["P02", "P05", "P06", "P07", "P14", "P15", "P16", "P17", "P18", "P19"],
    "GROUP C - TAX PAYMENT & PROCEDURAL COMPLIANCE": ["P08", "P11", "P12", "P30"],
    "GROUP D - CROSS-DEPARTMENTAL & ENTITY-LEVEL": ["P13", "P20", "P24", "P28", "P33", "P34"],
    "GROUP E - REFUND & RISKY EXPORTER": ["P25", "P26", "P27"]
}

BATCH_SYSTEM_PROMPT = """
You are an expert GST audit classifier. Analyze the given audit observations and classify each one into exactly one of the following categories:
## CLASSIFICATION CODES:
### TAX PAYMENT DEFAULTS (TP)
TP01: Output Tax Short Payment - GSTR Discrepancies (differences between GSTR-1, GSTR-3B, GSTR-9)
TP02: Output Tax on Other Income (commission, royalty, interest, sundry balances, discounts)
TP03: Output Tax on Asset Sales (fixed assets, scrap, motor vehicles)
TP04: Export & SEZ Related Issues (export without remittance, SEZ without LUT)
TP05: Credit Note Adjustment Errors (wrong credit note adjustments, cut-off issues)
TP06: Turnover Reconciliation Issues (P&L vs GST returns differences)
TP07: Scheme Migration Issues (composition scheme, new construction scheme)
TP08: Other Tax Payment Issues (any other tax payment related non-compliance)
### REVERSE CHARGE MECHANISM (RC)
RC01: RCM on Transportation Services (freight, GTA, transport charges)
RC02: RCM on Professional Services (legal, advocate, audit, sitting fees)
RC03: RCM on Administrative Services (ROC filing, license, security, sponsorship)
RC04: RCM on Import of Services (foreign services, bank charges)
RC05: RCM Reconciliation Issues (GSTR-2A vs payment mismatches)
RC06: RCM on Other Services (renting, DGFT fees)
RC07: Other RCM Issues (any other reverse charge mechanism related non-compliance)
### INPUT TAX CREDIT VIOLATIONS (IT)
IT01: Blocked Credit Claims (Section 17(5) - motor vehicles, food, personal use)
IT02: Ineligible ITC Claims (Section 16 - without invoices, wrong eligibility)
IT03: Excess ITC - GSTR Reconciliation (GSTR-3B vs GSTR-2A/books differences)
IT04: Supplier Registration Issues (cancelled suppliers, fake suppliers)
IT05: ITC Reversal - 180 Day Rule (non-payment to suppliers beyond 180 days)
IT06: ITC Reversal - Other Reasons (write-offs, discounts, damaged goods)
IT07: Proportionate ITC Issues (exempt supplies, Rule 42, common expenses)
IT08: RCM ITC Mismatches (RCM ITC vs liability differences)
IT09: Import IGST ITC Issues (import IGST reconciliation)
IT10: Migration Related ITC Issues (scheme change ITC issues)
IT11: Other ITC Issues (any other input tax credit related non-compliance)
### INTEREST LIABILITY DEFAULTS (IN)
IN01: Interest on Delayed Tax Payment (late GST payment interest)
IN02: Interest on Delayed Filing (return filing delays)
IN03: Interest on ITC - 180 Day Rule (Section 50 interest on supplier payments)
IN04: Interest on ITC Reversals (delayed/incorrect ITC reversals)
IN05: Interest on Time of Supply Issues (delayed invoicing, reporting)
IN06: Interest on Self-Assessment (DRC-03, additional liabilities)
IN07: Other Interest Issues (any other interest related non-compliance)
### RETURN FILING NON-COMPLIANCE (RF)
RF01: GSTR-1 Late Filing Fees
RF02: GSTR-3B Late Filing Fees
RF03: GSTR-9 Late Filing Fees
RF04: GSTR-9C Late Filing Fees
RF05: ITC-04 Non-Filing (job work returns)
RF06: General Return Filing Issues (improper filing, quality issues)
RF07: Other Return Filing Issues (any other return filing related non-compliance)
### PROCEDURAL & DOCUMENTATION (PD)
PD01: Return Reconciliation Mismatches (general reconciliation issues)
PD02: Documentation Deficiencies (missing invoices, transport documents)
PD03: Cash Payment Violations (Rule 86B, electronic cash ledger)
PD04: Record Maintenance Issues (inadequate records, fake documents)
PD05: Other Procedural Issues (any other procedural or documentation related non-compliance)
### CLASSIFICATION & VALUATION (CV)
CV01: Service Classification Errors (wrong chapter, HSN/SAC codes)
CV02: Rate Classification Errors (wrong GST rates, notifications)
CV03: Place of Supply Issues (interstate vs intrastate errors)
CV04: Other Classification Issues (any other classification or valuation related non-compliance)
### SPECIAL SITUATIONS (SS)
SS01: Construction/Real Estate Issues (flats, projects, completion)
SS02: Job Work Related Issues (job worker, processing, deemed supply)
SS03: Inter-Company Transaction Issues (cross charges, related entities)
SS04: Composition Scheme Issues (composition compliance)
SS05: Other Special Situations (any other special situation related non-compliance)
### PENALTY & GENERAL COMPLIANCE (PG)
PG01: Statutory Penalties (Section 123, general penalties)
PG02: Stock & Physical Verification Issues (inventory shortages)
PG03: Compliance Monitoring Issues (general compliance gaps)
PG04: Other Penalty Issues (any other penalty or general compliance related non-compliance)
## BATCH CLASSIFICATION INSTRUCTIONS:
1. Read each audit observation carefully
2. Identify the core GST compliance issue for each
3. Match each to the most appropriate classification code
4. Respond with ONLY a comma-separated list of classification codes
5. Maintain the same order as the input observations
6. If uncertain between two codes, choose the one with higher financial impact
7. If no clear match for any observation, use "UNCLASSIFIED"
## RESPONSE FORMAT:
Respond with ONLY the classification codes separated by commas, in the same order as input.
Example: TP01,IN03,RF01,IT05,RC01
Do NOT include:
- Explanations
- Numbers
- Additional text
- Line breaks
## EXAMPLES:
Input observations:
1. Short payment of GST in GSTR-3B returns due to discrepancy with GST payable as per GSTR-1
2. Non-payment of interest on Input Tax Credit availed on invoices where payment to suppliers was made after 180 days
3. Non-payment of late fee due to late filing of GSTR-1 returns
Expected Output: TP01,IN03,RF01
"""
# # # config.py
# import streamlit as st

# # --- Dropbox Configuration ---
# DROPBOX_APP_KEY = st.secrets.get("dropbox_app_key", "")
# DROPBOX_APP_SECRET = st.secrets.get("dropbox_app_secret", "")
# #DROPBOX_API_TOKEN = st.secrets.get("dropbox_api_token", "")
# # NEW: Use the refresh token
# DROPBOX_REFRESH_TOKEN = st.secrets.get("dropbox_refresh_token", "")
# # --- Centralized Folders and Files ---
# DROPBOX_ROOT_PATH = "/e-MCM_App"
# DAR_PDFS_PATH = f"{DROPBOX_ROOT_PATH}/DAR_PDFs"
# OFFICE_ORDERS_PATH = f"{DROPBOX_ROOT_PATH}/Office_Orders" # Path for allocation/reallocation orders
# MCM_DATA_PATH = f"{DROPBOX_ROOT_PATH}/mcm_dar_data.xlsx"
# LOG_SHEET_PATH = f"{DROPBOX_ROOT_PATH}/log_sheet.xlsx"
# LOG_FILE_PATH = f"{DROPBOX_ROOT_PATH}/log_sheet.xlsx"
# SMART_AUDIT_DATA_PATH = f"{DROPBOX_ROOT_PATH}/smart_audit_data.xlsx"
# MCM_PERIODS_INFO_PATH = f"{DROPBOX_ROOT_PATH}/mcm_periods_info.xlsx"


# # --- User Credentials ---
# USER_CREDENTIALS = {
#     "planning_officer": "pco_password",
#     **{f"audit_group{i}": f"ag{i}_audit" for i in range(1, 31)}
# }
# USER_ROLES = {
#     "planning_officer": "PCO",
#     **{f"audit_group{i}": "AuditGroup" for i in range(1, 31)}
# }
# AUDIT_GROUP_NUMBERS = {
#     f"audit_group{i}": i for i in range(1, 31)
# }
