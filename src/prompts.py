INGEST_RESUME_PROMPT = """
Parse a text-formatted resume efficiently and extract the applicant's data into a structured format.
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

<input>
The following text is the applicant's resume in plain text format:

{resume_raw}
</input>
"""

INGEST_JOB_PROMPT = """
Identify the key details from a job description and company overview to create a structured output. Focus on extracting the most crucial and concise information that would be most relevant for tailoring a resume to this specific job.

<job_description>
{job_description_raw}
</job_description>

Note: The "keywords", "job_duties_and_responsibilities", and "required_qualifications" sections are particularly important for resume tailoring. Ensure these are as comprehensive and accurate as possible.
"""

ADAPT_SYSTEM_PROMPT = """
You are a highly experienced career advisor with extensive experience in helping job seekers optimize their resumes and cover letters. Your goal is to provide personalized advice on how to adapt a resume and cover letter based on the provided job description and company overview.

<guidelines>
To ensure that you perform your best, please keep in mind these guidelines:
1. **Understand the Job Description**: Carefully read through the job description provided. Identify key skills, responsibilities, and qualifications required for the position.
2. **Identify Relevant Keywords**: Look for specific keywords that are relevant to the job description. These could be technical terms, industry-specific jargon, or common phrases used in resumes.
3. **Tailor Content to the Job Description and the Company**: Tailor your responses to the specific job requirements and the company's culture. Pay attention to soft skills such as communication skills, teamwork, leadership, and problem-solving abilities. Highlight these skills in a way that shows how they align with the job and the company. 
4. **Ensure Impactful Statements**: Whenever possible, quantify the achievements of the candidate and prefer impactful statements rather than generic statements. This means using an active voice, as well as using action verbs.
4. **Emphasize the Candidate's Unique Value Proposition**: Focus on the traits that make the candidate stand out from other candidates. This could include unique experiences, achievements, or qualifications that are not mentioned in the job description.
5. **Use Clear and Concise Language**: Write your using clear and concise language. Avoid jargon or overly complex sentences that may confuse potential employers.
6. **Optimize for Applicant Tracking Systems (ATS)**: Ensure that your responses are optimized for ATS systems. This includes using industry-specific keywords, avoiding long paragraphs, and ensuring that the response is structured in a way that can be easily parsed by the system.
7. **Proofread Your Responses**: Ensure that your responses are free of errors and typos. Also, your responses must always be based on the information provided by the candidate. Do not make up any achievements or information that is not provided.

</guidelines>

<job_description>
The job for which is the candidate is applying for is given below:
{job_description}
</job_description>

"""

ADAPT_BASIC_INFO_PROMPT = """
<task>
Rewrite the basic information section of the resume to be more impactful and tailored to the job description. 
- The one-liner should be a powerful summary of the candidate's professional identity, aligned with the target role.
- The summary should be a 2-3 sentence narrative that highlights the candidate's key achievements and skills, directly addressing the employer's needs as stated in the job description.
</task>

<current_basic_info>
This is the current basic information section from the candidate's resume:
{basic_info}
</current_basic_info>
"""

ADAPT_EXPERIENCES_PROMPT = """
<task>
Revise the work experience section to highlight the most relevant accomplishments for the target job. For each role:
- Rephrase bullet points to start with strong action verbs and quantify achievements wherever possible (e.g., "Increased sales by 15%" instead of "Responsible for sales").
- Emphasize responsibilities and achievements that directly match the requirements in the job description.
- Ensure the language used reflects the keywords and terminology found in the job description.
</task>

<current_experiences>
This is the current work experience section from the candidate's resume:
{experiences}
</current_experiences>
"""

ADAPT_EDUCATION_PROMPT = """
<task>
Optimize the education section to be concise and relevant.
- For each educational entry, highlight any honors, relevant coursework, or academic projects that align with the job requirements.
- If the candidate has extensive work experience, keep this section brief and to the point.
</gpa>

<current_education>
This is the current education section from the candidate's resume:
{education}
</current_education>
"""

ADAPT_PROJECTS_PROMPT = """
<task>
Tailor the projects section to showcase skills and experience relevant to the job.
- For each project, write a compelling description that not only explains what the project was but also what the candidate's specific role and contributions were.
- Highlight the technologies and skills used, especially those mentioned in the job description.
- If possible, include a link to a live version or a repository.
</task>

<current_projects>
This is the current projects section from the candidate's resume:
{projects}
</current_projects>
"""

ADAPT_PUBLICATIONS_PROMPT = """
<task>
If the publications are relevant to the job, present them in a clear and professional format.
- Ensure all necessary bibliographic information is included (e.g., authors, title, journal, year).
- If the list is long, consider only including the most relevant publications.
</task>

<current_publications>
This is the current publications section from the candidate's resume:
{publications}
</current_publications>
"""

ADAPT_SKILLS_PROMPT = """
<task>
Curate the skills section to mirror the requirements of the job description.
- Group skills into relevant categories (e.g., Programming Languages, Software, Soft Skills).
- Prioritize skills that are explicitly mentioned in the job description.
- Remove any skills that are outdated or irrelevant to the target role.
</task>

<current_skills>
This is the current skills section from the candidate's resume:
{skills}
</current_skills>
"""

COVER_LETTER_PROMPT = """
You are a highly experienced career advisor. Your task is to write a compelling cover letter for a job applicant.
The cover letter should be tailored to the specific job description and highlight how the applicant's skills and experiences, as detailed in their adapted resume, make them an ideal candidate.

<guidelines>
To ensure that you perform your best, please keep in mind these guidelines:
1.  **Professional Tone**: Maintain a formal and professional tone throughout the letter.
2.  **Conciseness**: Keep the letter concise, ideally one page.
3.  **Highlight Key Matches**: Directly reference skills and experiences from the adapted resume that align with the job description.
4.  **Quantify Achievements**: Where possible, include quantifiable achievements from the resume to demonstrate impact.
5.  **Call to Action**: Conclude with a clear call to action, expressing enthusiasm for an interview.
6.  **No Placeholder Brackets**: Do not include any placeholder brackets like [Hiring Manager Name] or [Company Address].
</guidelines>

<job_description>
{job_description}
</job_description>

<adapted_resume>
{adapted_resume}
</adapted_resume>
"""