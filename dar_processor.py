# dar_processor.py
import pdfplumber
import google.generativeai as genai
import json
import requests
import streamlit as st
from typing import List, Dict, Any, Tuple
from models import ParsedDARReport, DARHeaderSchema, AuditParaSchema
from config import BATCH_SYSTEM_PROMPT, TAXPAYER_CLASSIFICATION_OPTIONS

def preprocess_pdf_text(pdf_path_or_bytes) -> str:
    """
    Extracts all text from all pages of the PDF using pdfplumber,
    attempting to preserve layout for better LLM understanding.
    """
    processed_text_parts = []
    try:
        with pdfplumber.open(pdf_path_or_bytes) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=True)
                if page_text is None:
                    page_text = f"[INFO: Page {i + 1} yielded no text directly]"
                else:
                    page_text = page_text.replace("None", "")
                processed_text_parts.append(f"\n--- PAGE {i + 1} ---\n{page_text}")
        full_text = "".join(processed_text_parts)
        return full_text
    except Exception as e:
        error_msg = f"Error processing PDF with pdfplumber: {type(e).__name__} - {e}"
        print(error_msg)
        return error_msg

def get_structured_data_from_llm(text_content: str) -> ParsedDARReport:
    """
    Calls the OpenRouter API with the PDF text and parses the response.
    Returns a ParsedDARReport object.
    """
    if text_content.startswith("Error processing PDF"):
        return ParsedDARReport(parsing_errors=text_content)

    openrouter_api_key = st.secrets.get("openrouter_api_key", "")
    if not openrouter_api_key:
        error_msg = "OpenRouter API key not found in Streamlit secrets."
        return ParsedDARReport(parsing_errors=error_msg)

    prompt = f"""
    You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
    extract the specified information and structure it as a JSON object.

    The JSON object should follow this structure precisely:
    {{
      "header": {{
        "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
        "gstin": "string or null", "trade_name": "string or null", "category": "string ('Large', 'Medium', 'Small') or null",
        "taxpayer_classification": "string or null. Choose one from the following list: {TAXPAYER_CLASSIFICATION_OPTIONS}",
        "total_amount_detected_overall_rs": "float or null (in Rupees)",
        "total_amount_recovered_overall_rs": "float or null (in Rupees)",
        "risk_flags": "list of strings or null (e.g., ['P1', 'P04', 'P21'])"
      }},
      "audit_paras": [
        {{
          "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
          "audit_para_heading": "string or null (title of the para)",
          "revenue_involved_rs": "float or null ( in RUPEES)",
          "revenue_recovered_rs": "float or null ( in RUPEES)",
          "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
        }}
      ],
      "parsing_errors": "string or null"
    }}

    Key Instructions:
    1.  Header Info: Find all header fields.
    2.  Taxpayer Classification: Identify the taxpayer nature of business /activity/profile /serivce or goods provided  and Select the best fit for 'taxpayer_classification' from the provided list.
    3.  Risk Flags: Find all risk parameter codes mentioned, which look like P1, P2, P3... P34. Ignore any numbers in parentheses like P1(1). Collect only the codes (e.g., "P1").
    #4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts in the text. These amounts are often written as 'Rs. X,XX,XXX' or 'in Rupees'. Extract ONLY the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**.
    #4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts mentioned after the audit para headings in the text.Convert into the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**
    5.  If a value is not found, use null. All monetary values must be numbers (float).
    6.  The 'audit_paras' list should contain one object per para. If none found, provide an empty list [].
    
    DAR Text Content:
    --- START OF DAR TEXT ---
    {text_content}
    --- END OF DAR TEXT ---

    Provide ONLY the JSON object as your response. Do not include any explanatory text.
    """

    content_str_for_return = ""
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_api_key}"},
            data=json.dumps({
                "model": "deepseek/deepseek-r1:free",
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        if response.status_code != 200:
            error_text = f"API Error from OpenRouter: {response.status_code} - {response.text}"
            return ParsedDARReport(parsing_errors=error_text)

        response_data = response.json()
        content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        content_str_for_return = content_str
        
        if content_str.strip().startswith("```json"):
            content_str = content_str.strip()[7:-3].strip()
        elif content_str.strip().startswith("```"):
             content_str = content_str.strip()[3:-3].strip()
        
        if not content_str:
            return ParsedDARReport(parsing_errors="LLM returned an empty response.")
        
        json_data = json.loads(content_str)
        return ParsedDARReport(**json_data)
    except requests.exceptions.RequestException as e:
        return ParsedDARReport(parsing_errors=f"Network error calling OpenRouter API: {e}")
    except json.JSONDecodeError as e:
        err_msg = f"LLM output was not valid JSON: {e}. Raw response: {content_str_for_return[:500]}..."
        return ParsedDARReport(parsing_errors=err_msg)
    except Exception as e:
        return ParsedDARReport(parsing_errors=f"An unexpected error occurred: {e}")

def get_para_classifications_from_llm(audit_para_headings: List[str]) -> (List[str], str):
    openrouter_api_key = st.secrets.get("openrouter_api_key", "")
    if not openrouter_api_key:
        return [], "OpenRouter API key not found."
    formatted_observations = "\n".join([f"{i+1}. {heading}" for i, heading in enumerate(audit_para_headings)])
    user_prompt = f"Here are the audit observations to classify:\n{formatted_observations}"
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_api_key}"},
            data=json.dumps({
                "model": "deepseek/deepseek-r1:free",
                "messages": [
                    {"role": "system", "content": BATCH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]
            })
        )
        if response.status_code != 200:
            return [], f"API Error from OpenRouter: {response.status_code} - {response.text}"
        response_data = response.json()
        content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        if not content_str:
            return [], "LLM returned an empty response for classification."
        classifications = [code.strip() for code in content_str.split(',')]
        if len(classifications) != len(audit_para_headings):
            error_msg = f"Classification count mismatch. Expected {len(audit_para_headings)}, but got {len(classifications)}. Raw response: '{content_str}'"
            return classifications, error_msg
        return classifications, None
    except requests.exceptions.RequestException as e:
        return [], f"Network error during classification: {e}"
    except Exception as e:
        return [], f"An unexpected error occurred during classification: {e}"# # dar_processor.py
# import pdfplumber
# import google.generativeai as genai
# import json
# import requests
# import streamlit as st
# from typing import List, Dict, Any
# from models import ParsedDARReport, DARHeaderSchema, AuditParaSchema # Using your models.py
# from config import BATCH_SYSTEM_PROMPT, TAXPAYER_CLASSIFICATION_OPTIONS

# def preprocess_pdf_text(pdf_path_or_bytes) -> str:
#     """
#     Extracts all text from all pages of the PDF using pdfplumber,
#     attempting to preserve layout for better LLM understanding.
#     """
#     processed_text_parts = []
#     try:
#         with pdfplumber.open(pdf_path_or_bytes) as pdf:
#             for i, page in enumerate(pdf.pages):
#                 # Using layout=True helps preserve reading order for the LLM.
#                 page_text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=True)

#                 if page_text is None:
#                     page_text = f"[INFO: Page {i + 1} yielded no text directly]"
#                 else:
#                     # Basic sanitization
#                     page_text = page_text.replace("None", "")

#                 processed_text_parts.append(f"\n--- PAGE {i + 1} ---\n{page_text}")

#         full_text = "".join(processed_text_parts)
#         return full_text
#     except Exception as e:
#         error_msg = f"Error processing PDF with pdfplumber: {type(e).__name__} - {e}"
#         print(error_msg)
#         return error_msg

# # def get_structured_data_with_gemini(api_key: str, text_content: str) -> ParsedDARReport:
# #     """
# #     Calls the Gemini API with the PDF text and parses the response.
# #     This version keeps all monetary values in Rupees as requested.
# #     """
# #     if text_content.startswith("Error processing PDF"):
# #         return ParsedDARReport(parsing_errors=text_content)

# #     genai.configure(api_key=api_key)
# #     model = genai.GenerativeModel('gemini-1.5-flash-latest')

# #     # --- MODIFIED PROMPT ---
# #     prompt = f"""
# #     You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
# #     extract the specified information and structure it as a JSON object.

# #     The JSON object should follow this structure precisely:
# #     {{
# #       "header": {{
# #         "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
# #         "gstin": "string or null",
# #         "trade_name": "string or null",
# #         "category": "string ('Large', 'Medium', 'Small') or null",
# #         "taxpayer_classification": "string or null. Choose one from the following list: {TAXPAYER_CLASSIFICATION_OPTIONS}",
# #         "total_amount_detected_overall_rs": "float or null (in Rupees)",
# #         "total_amount_recovered_overall_rs": "float or null (in Rupees)",
# #         "risk_flags": "list of strings or null (e.g., ['P1', 'P04', 'P21'])"
# #       }},
# #       "audit_paras": [
# #         {{
# #           "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
# #           "audit_para_heading": "string or null (title of the para)",
# #           "revenue_involved_rs": "float or null (Value MUST be in RUPEES)",
# #           "revenue_recovered_rs": "float or null (Value MUST be in RUPEES)",
# #           "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
# #         }}
# #       ],
# #       "parsing_errors": "string or null"
# #     }}

# #     Key Instructions:
# #     1.  Header Info: Find all header fields.
# #     2.  Taxpayer Classification: Select the best fit for 'taxpayer_classification' from the provided list.
# #     3.  Risk Flags: Find all risk parameter codes mentioned, which look like P1, P2, P3... P34. Ignore any numbers in parentheses like P1(1). Collect only the codes (e.g., "P1").
# #     4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts in the text. These amounts are often written as 'Rs. X,XX,XXX' or 'in Rupees'. Extract ONLY the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**.
# #     5.  If a value is not found, use null.
# #     6.  The 'audit_paras' list should contain one object per para. If none are found, provide an empty list [].

# #     DAR Text Content:
# #     --- START OF DAR TEXT ---
# #     {text_content}
# #     --- END OF DAR TEXT ---

# #     Provide ONLY the JSON object as your response. Do not include any explanatory text.
# #     """

# #     try:
# #         response = model.generate_content(prompt)

# #         cleaned_response_text = response.text.strip()
# #         if cleaned_response_text.startswith("```json"):
# #             cleaned_response_text = cleaned_response_text[7:-3].strip()
# #         elif cleaned_response_text.startswith("```"):
# #              cleaned_response_text = cleaned_response_text[3:-3].strip()


# #         if not cleaned_response_text:
# #             return ParsedDARReport(parsing_errors="Gemini returned an empty response.")

# #         # Parse and validate the JSON data using Pydantic models
# #         json_data = json.loads(cleaned_response_text)
# #         return ParsedDARReport(**json_data)

# #     except json.JSONDecodeError as e:
# #         raw_response = "Response object not available"
# #         if 'response' in locals() and hasattr(response, 'text'):
# #             raw_response = response.text
# #         return ParsedDARReport(parsing_errors=f"Gemini output was not valid JSON: {e}. Raw response: {raw_response[:500]}...")
# #     except Exception as e:
# #         return ParsedDARReport(parsing_errors=f"An unexpected error occurred during Gemini processing: {e}")


# # def get_structured_data_from_llm(text_content: str) -> ParsedDARReport:
# #     """
# #     Calls the OpenRouter API with the PDF text and parses the response.
# #     This version keeps all monetary values in Rupees as requested.
# #     """
# #     if text_content.startswith("Error processing PDF"):
# #         return ParsedDARReport(parsing_errors=text_content)

# #     openrouter_api_key = st.secrets.get("openrouter_api_key", "")
# #     if not openrouter_api_key:
# #         error_msg = "OpenRouter API key not found in Streamlit secrets."
# #         return ParsedDARReport(parsing_errors=error_msg)

# #     prompt = f"""
# #     You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
# #     extract the specified information and structure it as a JSON object.

# #     The JSON object should follow this structure precisely:
# #     {{
# #       "header": {{
# #         "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
# #         "gstin": "string or null", "trade_name": "string or null", "category": "string ('Large', 'Medium', 'Small') or null",
# #         "taxpayer_classification": "string or null. Choose one from the following list: {TAXPAYER_CLASSIFICATION_OPTIONS}",
# #         "total_amount_detected_overall_rs": "float or null (in Rupees)",
# #         "total_amount_recovered_overall_rs": "float or null (in Rupees)",
# #         "risk_flags": "list of strings or null (e.g., ['P1', 'P04', 'P21'])"
# #       }},
# #       "audit_paras": [
# #         {{
# #           "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
# #           "audit_para_heading": "string or null (title of the para)",
# #           "revenue_involved_rs": "float or null ( in RUPEES)",
# #           "revenue_recovered_rs": "float or null ( in RUPEES)",
# #           "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
# #         }}
# #       ],
# #       "parsing_errors": "string or null"
# #     }}

# #     Key Instructions:
# #     1.  Header Info: Find all header fields.
# #     2.  Taxpayer Classification: Identify the taxpayer nature of business /activity/profile /serivce or goods provided  and Select the best fit for 'taxpayer_classification' from the provided list.
# #     3.  Risk Flags: Find all risk parameter codes mentioned, which look like P1, P2, P3... P34. Ignore any numbers in parentheses like P1(1). Collect only the codes (e.g., "P1").
# #     #4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts in the text. These amounts are often written as 'Rs. X,XX,XXX' or 'in Rupees'. Extract ONLY the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**.
# #     #4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts mentioned after the audit para headings in the text.Convert into the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**
# #     5.  If a value is not found, use null. All monetary values must be numbers (float).
# #     6.  The 'audit_paras' list should contain one object per para. If none found, provide an empty list [].

# #     DAR Text Content:
# #     --- START OF DAR TEXT ---
# #     {text_content}
# #     --- END OF DAR TEXT ---

# #     Provide ONLY the JSON object as your response. Do not include any explanatory text before or after the JSON.
# #     """

# #     try:
# #         response = requests.post(
# #             url="https://openrouter.ai/api/v1/chat/completions",
# #             headers={
# #                 "Authorization": f"Bearer {openrouter_api_key}",
# #             },
# #             data=json.dumps({
# #                 "model": "deepseek/deepseek-r1:free",
# #                 "messages": [{"role": "user", "content": prompt}]
# #             })
# #         )

# #         if response.status_code != 200:
# #             error_message = f"API Error from OpenRouter: {response.status_code} - {response.text}"
# #             return ParsedDARReport(parsing_errors=error_message)

# #         response_data = response.json()
# #         content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')

# #         if content_str.strip().startswith("```json"):
# #             content_str = content_str.strip()[7:-3].strip()
# #         elif content_str.strip().startswith("```"):
# #              content_str = content_str.strip()[3:-3].strip()
# #          # --- ADDED FOR DEBUGGING ---
# #         print("--- RAW LLM RESPONSE (OpenRouter) ---")
# #         print(content_str)
# #         print("--------------------------------------")
# #         # ---------------------------

# #         if not content_str:
# #             return ParsedDARReport(parsing_errors="LLM returned an empty response.")

# #         json_data = json.loads(content_str)
# #         return ParsedDARReport(**json_data)

# #     except requests.exceptions.RequestException as e:
# #         return ParsedDARReport(parsing_errors=f"Network error calling OpenRouter API: {e}")
# #     except json.JSONDecodeError as e:
# #         return ParsedDARReport(parsing_errors=f"LLM output was not valid JSON: {e}. Raw response: {content_str[:500]}...")
# #     except Exception as e:
# #         return ParsedDARReport(parsing_errors=f"An unexpected error occurred: {e}")

# # def get_para_classifications_from_llm(audit_para_headings: List[str]) -> (List[str], str):
# #     """
# #     Calls the OpenRouter API to classify a batch of audit para headings.
# #     Returns a tuple: (list_of_codes, error_message_or_none).
# #     """
# #     openrouter_api_key = st.secrets.get("openrouter_api_key", "")
# #     if not openrouter_api_key:
# #         return [], "OpenRouter API key not found."

# #     formatted_observations = "\n".join([f"{i+1}. {heading}" for i, heading in enumerate(audit_para_headings)])
# #     user_prompt = f"Here are the audit observations to classify:\n{formatted_observations}"

# #     try:
# #         response = requests.post(
# #             url="https://openrouter.ai/api/v1/chat/completions",
# #             headers={"Authorization": f"Bearer {openrouter_api_key}"},
# #             data=json.dumps({
# #                  #"model": "deepseek/deepseek-r1:free",
# #                 "model": "tngtech/deepseek-r1t2-chimera:free",
# #                 "messages": [
# #                     {"role": "system", "content": BATCH_SYSTEM_PROMPT},
# #                     {"role": "user", "content": user_prompt}
# #                 ]
# #             })
# #         )

# #         if response.status_code != 200:
# #             return [], f"API Error from OpenRouter: {response.status_code} - {response.text}"

# #         response_data = response.json()
# #         content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

# #         if not content_str:
# #             return [], "LLM returned an empty response for classification."

# #         # The prompt asks for a comma-separated list.
# #         classifications = [code.strip() for code in content_str.split(',')]

# #         if len(classifications) != len(audit_para_headings):
# #             error_msg = f"Classification count mismatch. Expected {len(audit_para_headings)}, but got {len(classifications)}. Raw response: '{content_str}'"
# #             # Return what we got, along with the error, for debugging.
# #             return classifications, error_msg

# #         return classifications, None

# #     except requests.exceptions.RequestException as e:
# #         return [], f"Network error during classification: {e}"
# #     except Exception as e:
# #         return [], f"An unexpected error occurred during classification: {e}"# # dar_processor.py

# def get_structured_data_from_llm(text_content: str) -> ParsedDARReport:
#     """
#     Calls the OpenRouter API with the PDF text and parses the response.
#     This version keeps all monetary values in Rupees as requested.
#     """
#     if text_content.startswith("Error processing PDF"):
#         return ParsedDARReport(parsing_errors=text_content)

#     openrouter_api_key = st.secrets.get("openrouter_api_key", "")
#     if not openrouter_api_key:
#         error_msg = "OpenRouter API key not found in Streamlit secrets."
#         return ParsedDARReport(parsing_errors=error_msg)

#     prompt = f"""
#     You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
#     extract the specified information and structure it as a JSON object.

#     The JSON object should follow this structure precisely:
#     {{
#       "header": {{
#         "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
#         "gstin": "string or null", "trade_name": "string or null", "category": "string ('Large', 'Medium', 'Small') or null",
#         "taxpayer_classification": "string or null. Choose one from the following list: {TAXPAYER_CLASSIFICATION_OPTIONS}",
#         "total_amount_detected_overall_rs": "float or null (in Rupees)",
#         "total_amount_recovered_overall_rs": "float or null (in Rupees)",
#         "risk_flags": "list of strings or null (e.g., ['P1', 'P04', 'P21'])"
#       }},
#       "audit_paras": [
#         {{
#           "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
#           "audit_para_heading": "string or null (title of the para)",
#           "revenue_involved_rs": "float or null ( in RUPEES)",
#           "revenue_recovered_rs": "float or null ( in RUPEES)",
#           "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
#         }}
#       ],
#       "parsing_errors": "string or null"
#     }}

#     Key Instructions:
#     1.  Header Info: Find all header fields.
#     2.  Taxpayer Classification: Identify the taxpayer nature of business /activity/profile /serivce or goods provided  and Select the best fit for 'taxpayer_classification' from the provided list.
#     3.  Risk Flags: Find all risk parameter codes mentioned, which look like P1, P2, P3... P34. Ignore any numbers in parentheses like P1(1). Collect only the codes (e.g., "P1").
#     #4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts in the text. These amounts are often written as 'Rs. X,XX,XXX' or 'in Rupees'. Extract ONLY the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**.
#     #4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts mentioned after the audit para headings in the text.Convert into the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**
#     5.  If a value is not found, use null. All monetary values must be numbers (float).
#     6.  The 'audit_paras' list should contain one object per para. If none found, provide an empty list [].

#     DAR Text Content:
#     --- START OF DAR TEXT ---
#     {text_content}
#     --- END OF DAR TEXT ---

#     Provide ONLY the JSON object as your response. Do not include any explanatory text before or after the JSON.
#     """

#     try:
#         response = requests.post(
#             url="https://openrouter.ai/api/v1/chat/completions",
#             headers={
#                 "Authorization": f"Bearer {openrouter_api_key}",
#             },
#             data=json.dumps({
#                 "model": "deepseek/deepseek-r1:free",
#                 "messages": [{"role": "user", "content": prompt}]
#             })
#         )

#         if response.status_code != 200:
#             error_message = f"API Error from OpenRouter: {response.status_code} - {response.text}"
#             return ParsedDARReport(parsing_errors=error_message)

#         response_data = response.json()
#         content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')

#         # --- DISPLAY RAW OUTPUT IN STREAMLIT UI ---
#         st.markdown("### 🔍 **Raw LLM Response Debug**")
#         with st.expander("Click to view raw LLM output", expanded=False):
#             st.text_area(
#                 "Raw API Response:",
#                 value=content_str,
#                 height=300,
#                 disabled=True,
#                 key=f"raw_output_{hash(content_str[:100])}"
#             )
#         # ----------------------------------------

#         if content_str.strip().startswith("```json"):
#             content_str = content_str.strip()[7:-3].strip()
#         elif content_str.strip().startswith("```"):
#              content_str = content_str.strip()[3:-3].strip()
         
#         # --- ALSO SHOW CLEANED VERSION ---
#         with st.expander("Click to view cleaned JSON", expanded=False):
#             st.text_area(
#                 "Cleaned JSON:",
#                 value=content_str,
#                 height=200,
#                 disabled=True,
#                 key=f"cleaned_output_{hash(content_str[:100])}"
#             )
#         # --------------------------------

#         # --- ADDITIONAL: Print to console (for local development) ---
#         print("=" * 60)
#         print("RAW LLM RESPONSE (OpenRouter)")
#         print("=" * 60)
#         print(content_str)
#         print("=" * 60)
#         # --------------------------------------------------------

#         if not content_str:
#             return ParsedDARReport(parsing_errors="LLM returned an empty response.")

#         json_data = json.loads(content_str)
#         return ParsedDARReport(**json_data)

#     except requests.exceptions.RequestException as e:
#         return ParsedDARReport(parsing_errors=f"Network error calling OpenRouter API: {e}")
#     except json.JSONDecodeError as e:
#         return ParsedDARReport(parsing_errors=f"LLM output was not valid JSON: {e}. Raw response: {content_str[:500]}...")
#     except Exception as e:
#         return ParsedDARReport(parsing_errors=f"An unexpected error occurred: {e}")


# def get_para_classifications_from_llm(audit_para_headings: List[str]) -> (List[str], str):
#     """
#     Calls the OpenRouter API to classify a batch of audit para headings.
#     Returns a tuple: (list_of_codes, error_message_or_none).
#     """
#     openrouter_api_key = st.secrets.get("openrouter_api_key", "")
#     if not openrouter_api_key:
#         return [], "OpenRouter API key not found."

#     formatted_observations = "\n".join([f"{i+1}. {heading}" for i, heading in enumerate(audit_para_headings)])
#     user_prompt = f"Here are the audit observations to classify:\n{formatted_observations}"

#     try:
#         response = requests.post(
#             url="https://openrouter.ai/api/v1/chat/completions",
#             headers={"Authorization": f"Bearer {openrouter_api_key}"},
#             data=json.dumps({
#                  #"model": "deepseek/deepseek-r1:free",
#                 "model": "tngtech/deepseek-r1t2-chimera:free",
#                 "messages": [
#                     {"role": "system", "content": BATCH_SYSTEM_PROMPT},
#                     {"role": "user", "content": user_prompt}
#                 ]
#             })
#         )

#         if response.status_code != 200:
#             return [], f"API Error from OpenRouter: {response.status_code} - {response.text}"

#         response_data = response.json()
#         content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

#         # --- DISPLAY CLASSIFICATION RAW OUTPUT ---
#         st.markdown("### 🏷️ **Classification Response Debug**")
#         with st.expander("Click to view classification raw output", expanded=False):
#             st.text_area(
#                 "Classification API Response:",
#                 value=content_str,
#                 height=150,
#                 disabled=True,
#                 key=f"classification_output_{hash(content_str[:50])}"
#             )
#         # ----------------------------------------

#         # --- Print to console ---
#         print("=" * 40)
#         print("CLASSIFICATION RESPONSE")
#         print("=" * 40)
#         print(content_str)
#         print("=" * 40)
#         # -----------------------

#         if not content_str:
#             return [], "LLM returned an empty response for classification."

#         # The prompt asks for a comma-separated list.
#         classifications = [code.strip() for code in content_str.split(',')]

#         if len(classifications) != len(audit_para_headings):
#             error_msg = f"Classification count mismatch. Expected {len(audit_para_headings)}, but got {len(classifications)}. Raw response: '{content_str}'"
#             # Return what we got, along with the error, for debugging.
#             return classifications, error_msg

#         return classifications, None

#     except requests.exceptions.RequestException as e:
#         return [], f"Network error during classification: {e}"
#     except Exception as e:
#         return [], f"An unexpected error occurred during classification: {e}"



# # import pdfplumber
# # import google.generativeai as genai
# # import json
# # import requests
# # import streamlit as st
# # from typing import List, Dict, Any
# # from models import ParsedDARReport, DARHeaderSchema, AuditParaSchema # Using your models.py

# # def preprocess_pdf_text(pdf_path_or_bytes) -> str:
# #     """
# #     Extracts all text from all pages of the PDF using pdfplumber,
# #     attempting to preserve layout for better LLM understanding.
# #     """
# #     processed_text_parts = []
# #     try:
# #         with pdfplumber.open(pdf_path_or_bytes) as pdf:
# #             for i, page in enumerate(pdf.pages):
# #                 # Using layout=True helps preserve reading order for the LLM.
# #                 page_text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=True)

# #                 if page_text is None:
# #                     page_text = f"[INFO: Page {i + 1} yielded no text directly]"
# #                 else:
# #                     # Basic sanitization
# #                     page_text = page_text.replace("None", "")

# #                 processed_text_parts.append(f"\n--- PAGE {i + 1} ---\n{page_text}")

# #         full_text = "".join(processed_text_parts)
# #         return full_text
# #     except Exception as e:
# #         error_msg = f"Error processing PDF with pdfplumber: {type(e).__name__} - {e}"
# #         print(error_msg)
# #         return error_msg

# # def get_structured_data_with_gemini(api_key: str, text_content: str) -> ParsedDARReport:
# #     """
# #     Calls the Gemini API with the PDF text and parses the response.
# #     This version keeps all monetary values in Rupees as requested.
# #     """
# #     if text_content.startswith("Error processing PDF"):
# #         return ParsedDARReport(parsing_errors=text_content)

# #     genai.configure(api_key=api_key)
# #     model = genai.GenerativeModel('gemini-1.5-flash-latest')

# #     # --- MODIFIED PROMPT ---
# #     # Instructions now explicitly state to keep all values in Rupees.
# #     prompt = f"""
# #     You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
# #     extract the specified information and structure it as a JSON object.

# #     The JSON object should follow this structure precisely:
# #     {{
# #       "header": {{
# #         "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
# #         "gstin": "string or null",
# #         "trade_name": "string or null",
# #         "category": "string ('Large', 'Medium', 'Small') or null",
# #         "total_amount_detected_overall_rs": "float or null (in Rupees)",
# #         "total_amount_recovered_overall_rs": "float or null (in Rupees)"
# #       }},
# #       "audit_paras": [
# #         {{
# #           "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
# #           "audit_para_heading": "string or null (title of the para)",
# #           "revenue_involved_lakhs_rs": "float or null (Value MUST be in RUPEES)",
# #           "revenue_recovered_lakhs_rs": "float or null (Value MUST be in RUPEES)",
# #           "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
# #         }}
# #       ],
# #       "parsing_errors": "string or null"
# #     }}

# #     Key Instructions:
# #     1.  Header Info: Find `audit_group_number`, `gstin`, `trade_name`, `category`, and overall totals. These totals should be in Rupees.
# #     2.  Audit Paras: Identify each para. Extract `audit_para_number`, `audit_para_heading`, and `status_of_para`.
# #     3.  **CRITICAL**: For `revenue_involved_lakhs_rs` and `revenue_recovered_lakhs_rs`, extract the monetary value directly in **Rupees**. DO NOT convert the amount to Lakhs, even though 'lakhs' is in the field name. The value must be a float.
# #     4.  If a value is not found, use null. All monetary values must be numbers (float).
# #     5.  The 'audit_paras' list should contain one object per para. If none are found, provide an empty list [].

# #     DAR Text Content:
# #     --- START OF DAR TEXT ---
# #     {text_content}
# #     --- END OF DAR TEXT ---

# #     Provide ONLY the JSON object as your response. Do not include any explanatory text before or after the JSON.
# #     """

# #     try:
# #         response = model.generate_content(prompt)

# #         cleaned_response_text = response.text.strip()
# #         if cleaned_response_text.startswith("```json"):
# #             cleaned_response_text = cleaned_response_text[7:-3].strip()
# #         elif cleaned_response_text.startswith("```"):
# #              cleaned_response_text = cleaned_response_text[3:-3].strip()


# #         if not cleaned_response_text:
# #             return ParsedDARReport(parsing_errors="Gemini returned an empty response.")

# #         # Parse and validate the JSON data using Pydantic models
# #         json_data = json.loads(cleaned_response_text)
# #         return ParsedDARReport(**json_data)

# #     except json.JSONDecodeError as e:
# #         raw_response = "Response object not available"
# #         if 'response' in locals() and hasattr(response, 'text'):
# #             raw_response = response.text
# #         return ParsedDARReport(parsing_errors=f"Gemini output was not valid JSON: {e}. Raw response: {raw_response[:500]}...")
# #     except Exception as e:
# #         return ParsedDARReport(parsing_errors=f"An unexpected error occurred during Gemini processing: {e}")


# # def get_structured_data_from_llm(text_content: str) -> ParsedDARReport:
# #     """
# #     Calls the OpenRouter API with the PDF text and parses the response.
# #     This version keeps all monetary values in Rupees as requested.
# #     """
# #     if text_content.startswith("Error processing PDF"):
# #         return ParsedDARReport(parsing_errors=text_content)

# #     openrouter_api_key = st.secrets.get("openrouter_api_key", "")
# #     if not openrouter_api_key:
# #         error_msg = "OpenRouter API key not found in Streamlit secrets."
# #         return ParsedDARReport(parsing_errors=error_msg)

# #     # --- MODIFIED PROMPT ---
# #     # Instructions now explicitly state to keep all values in Rupees.
# #     prompt = f"""
# #     You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
# #     extract the specified information and structure it as a JSON object.

# #     The JSON object should follow this structure precisely:
# #     {{
# #       "header": {{
# #         "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
# #         "gstin": "string or null", "trade_name": "string or null", "category": "string ('Large', 'Medium', 'Small') or null",
# #         "total_amount_detected_overall_rs": "float or null (in Rupees)",
# #         "total_amount_recovered_overall_rs": "float or null (in Rupees)"
# #       }},
# #       "audit_paras": [
# #         {{
# #           "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
# #           "audit_para_heading": "string or null (title of the para)",
# #           "revenue_involved_lakhs_rs": "float or null (Value MUST be in RUPEES)",
# #           "revenue_recovered_lakhs_rs": "float or null (Value MUST be in RUPEES)",
# #           "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
# #         }}
# #       ],
# #       "parsing_errors": "string or null"
# #     }}

# #     Key Instructions:
# #     1.  Header Info: Find `audit_group_number`, `gstin`, `trade_name`, `category`, and overall totals in Rupees.
# #     2.  Audit Paras: Identify each para. Extract `audit_para_number`, `audit_para_heading`, and `status_of_para`.
# #     3.  **CRITICAL**: For `revenue_involved_lakhs_rs` and `revenue_recovered_lakhs_rs`, extract the monetary value directly in **Rupees**. DO NOT convert the amount to Lakhs, even though 'lakhs' is in the field name. The value must be a float.
# #     4.  If a value is not found, use null. All monetary values must be numbers (float).
# #     5.  The 'audit_paras' list should contain one object per para. If none found, provide an empty list [].

# #     DAR Text Content:
# #     --- START OF DAR TEXT ---
# #     {text_content}
# #     --- END OF DAR TEXT ---

# #     Provide ONLY the JSON object as your response. Do not include any explanatory text before or after the JSON.
# #     """

# #     try:
# #         response = requests.post(
# #             url="https://openrouter.ai/api/v1/chat/completions",
# #             headers={
# #                 "Authorization": f"Bearer {openrouter_api_key}",
# #             },
# #             data=json.dumps({
# #                 "model": "deepseek/deepseek-r1:free",
# #                 "messages": [{"role": "user", "content": prompt}]
# #             })
# #         )

# #         if response.status_code != 200:
# #             error_message = f"API Error from OpenRouter: {response.status_code} - {response.text}"
# #             return ParsedDARReport(parsing_errors=error_message)

# #         response_data = response.json()
# #         content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        
# #         # Clean up markdown code block if present
# #         if content_str.strip().startswith("```json"):
# #             content_str = content_str.strip()[7:-3].strip()
# #         elif content_str.strip().startswith("```"):
# #              content_str = content_str.strip()[3:-3].strip()

# #         if not content_str:
# #             return ParsedDARReport(parsing_errors="LLM returned an empty response.")

# #         # Parse and validate the JSON data using Pydantic models
# #         json_data = json.loads(content_str)
# #         return ParsedDARReport(**json_data)

# #     except requests.exceptions.RequestException as e:
# #         return ParsedDARReport(parsing_errors=f"Network error calling OpenRouter API: {e}")
# #     except json.JSONDecodeError as e:
# #         return ParsedDARReport(parsing_errors=f"LLM output was not valid JSON: {e}. Raw response: {content_str[:500]}...")
# #     except Exception as e:
# #         return ParsedDARReport(parsing_errors=f"An unexpected error occurred: {e}")# # dar_processor.py
