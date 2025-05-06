INGEST_RESUME_PROMPT = """<objective>
Parse a text-formatted resume efficiently and extract the applicant's data into a structured format.
</objective>

<input>
The following text is the applicant's resume in plain text format:

{resume_raw}
</input>

<instructions>
Follow these steps to extract and structure the resume information:

1. Analyze Structure:
   - Examine the text-formatted resume to identify key sections (e.g., personal information, education, experience, skills, certifications).
   - Note any unique formatting or organization within the resume.

2. Extract Information:
   - Systematically parse each section, extracting relevant details. Ensure that you reproduce details verbatim from the original text. Do not include any additional context or explanations beyond what's directly stated in the text.
   - Pay attention to dates, titles, organizations, and descriptions.
   - Ensure that all the information in the text is extracted.

3. Handle Variations:
   - Account for different resume styles, formats, and section orders.
   - Adapt the extraction process to accurately capture data from various layouts.

5. Optimize Output:
   - Handle missing or incomplete information appropriately (use null values or empty arrays/objects as needed).
   - Standardize date formats, if applicable.

6. Validate:
   - Review the extracted data for consistency and completeness.
   - Ensure all required fields are populated if the information is available in the resume.
</instructions>"""

INGEST_JOB_PROMPT = """
<task>
Identify the key details from a job description and company overview to create a structured output. Focus on extracting the most crucial and concise information that would be most relevant for tailoring a resume to this specific job.
</task>

<job_description>
{job_description_raw}
</job_description>

Note: The "keywords", "job_duties_and_responsibilities", and "required_qualifications" sections are particularly important for resume tailoring. Ensure these are as comprehensive and accurate as possible.
"""