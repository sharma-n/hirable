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

4. Optimize Output:
   - Handle missing or incomplete information appropriately (use null values or empty arrays/objects as needed).
   - Standardize date formats, if applicable.

5. Validate:
   - Review the extracted data for consistency and completeness.
   - Ensure all required fields are populated if the information is available in the resume.
</instructions>
"""

INGEST_JOB_PROMPT = """<task>
Identify the key details from a job description and company overview to create a structured output. Focus on extracting the most crucial and concise information that would be most relevant for tailoring a resume to this specific job.
</task>

<instructions>
1. **Keywords**: Extract all relevant keywords that appear in the job description. These should include technical skills, soft skills, industry-specific terms, and any other terms that an Applicant Tracking System (ATS) might look for.
2. **Job Duties and Responsibilities**: Summarize the core duties and responsibilities of the role as described in the job description. Focus on action-oriented statements.
3. **Required Qualifications**: List all mandatory qualifications, including educational requirements, years of experience, specific certifications, and essential skills.
4. **Desired Qualifications**: List any preferred but not mandatory qualifications.
5. **Company Description**: Briefly summarize the company's mission, values, and any relevant information that might help in tailoring a resume or cover letter.
6. **Location**: Extract the job location.
</instructions>

<job_description>
{job_description_raw}
</job_description>

Note: The "keywords", "job_duties_and_responsibilities", and "required_qualifications" sections are particularly important for resume tailoring. Ensure these are as comprehensive and accurate as possible.
"""

ADAPT_SYSTEM_PROMPT = """
I am a highly experienced career advisor and resume writing expert with 15 years of specialized experience.

Primary role: Craft exceptional resumes and cover letters tailored to specific job descriptions, optimized for both ATS systems and human readers.

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

ADAPT_BASIC_INFO_PROMPT = """<task>
Rewrite the basic information section of the resume to be more impactful and tailored to the job description. 
</task>

<instructions>
1. **One-liner**: Craft a powerful, concise one-liner (professional headline) that summarizes the candidate's professional identity and aligns directly with the target role and industry.
2. **Summary**: Develop a 2-3 sentence narrative summary that highlights the candidate's most relevant achievements, skills, and career goals, directly addressing the employer's needs as stated in the job description.
3. **Keywords**: Naturally integrate keywords from the job description into both the one-liner and summary to optimize for Applicant Tracking Systems (ATS).
4. **Impact**: Ensure the summary emphasizes the candidate's potential contributions and value to the prospective employer.
</instructions>

<current_basic_info>
This is the current basic information section from the candidate's resume:
{basic_info}
</current_basic_info>

<example_of_good_resume_text>
**One-liner Example:**
"Highly motivated Software Engineer with expertise in scalable backend systems and cloud infrastructure."

**Summary Example:**
"Results-oriented Software Engineer with 5+ years of experience in developing and deploying robust web applications. Proven ability to lead cross-functional teams and deliver high-quality code, consistently exceeding project goals. Seeking to leverage strong problem-solving skills and technical acumen to contribute to innovative solutions at [Company Name]."
</example_of_good_resume_text>
"""

ADAPT_EXPERIENCES_PROMPT = """<task>
Revise the work experience section to highlight the most relevant accomplishments for the target job.
</task>

<instructions>
1. **Relevance**: Prioritize experiences and achievements that directly align with the job description's requirements and responsibilities.
2. **Action Verbs**: Start each bullet point with a strong action verb to convey impact and initiative.
3. **Quantify Achievements**: Wherever possible, quantify accomplishments with numbers, percentages, or specific outcomes (e.g., "Increased sales by 15%" instead of "Responsible for sales").
4. **STAR Method**: Implicitly use the STAR (Situation, Task, Action, Result) method within bullet points to provide context and demonstrate impact.
5. **Keywords**: Integrate keywords and terminology from the job description naturally into the descriptions.
6. **Conciseness**: Keep bullet points concise and impactful, typically 1-2 lines each.
7. **Truthfulness**: Ensure all information is accurate and verifiable.
</instructions>

<current_experiences>
This is the current work experience section from the candidate's resume:
{experiences}
</current_experiences>
"""

ADAPT_EDUCATION_PROMPT = """<task>
Optimize the education section to be concise and relevant.
</task>

<instructions>
1. **Relevance**: Highlight educational achievements, coursework, and academic projects that are directly relevant to the job description.
2. **Conciseness**: For candidates with extensive work experience, keep the education section brief and to the point.
3. **Honors and Awards**: Include any honors, scholarships, or academic awards received.
4. **Keywords**: Integrate relevant keywords from the job description into descriptions of coursework or projects.
5. **Clarity**: Ensure dates, degrees, and institutions are clearly stated.
</instructions>

<current_education>
This is the current education section from the candidate's resume:
{education}
</current_education>
"""

ADAPT_PROJECTS_PROMPT = """<task>
Tailor the projects section to showcase skills and experience relevant to the job.
</task>

<instructions>
1. **Relevance**: Select projects that are most relevant to the target job description, highlighting skills and technologies mentioned.
2. **Impact**: For each project, describe the candidate's specific role, contributions, and the impact of their work. Quantify achievements where possible.
3. **Technologies**: Clearly list the technologies, tools, and methodologies used in each project, especially those aligning with the job requirements.
4. **Links**: If available, include links to live versions, GitHub repositories, or project portfolios.
5. **Conciseness**: Keep project descriptions concise and focused on outcomes.
</instructions>

<current_projects>
This is the current projects section from the candidate's resume:
{projects}
</current_projects>
"""

ADAPT_PUBLICATIONS_PROMPT = """<task>
If the publications are relevant to the job, present them in a clear and professional format.
</task>

<instructions>
1. **Relevance**: Include publications that are directly relevant to the target job or demonstrate valuable skills (e.g., research, writing, analytical skills).
2. **Completeness**: Ensure all necessary bibliographic information is included (e.g., authors, title, journal/conference, year, volume, pages).
3. **Conciseness**: If the candidate has a long list of publications, consider only including the most impactful and relevant ones.
4. **Formatting**: Present publications in a consistent and professional citation style.
5. **Impact**: Briefly describe the significance or impact of the publication if it adds value to the application.
</instructions>

<current_publications>
This is the current publications section from the candidate's resume:
{publications}
</current_publications>
"""

ADAPT_SKILLS_PROMPT = """<task>
Curate the skills section to mirror the requirements of the job description.
</task>

<instructions>
1. **Relevance**: Prioritize and include skills that are explicitly mentioned or strongly implied in the job description.
2. **Categorization**: Group skills into logical and relevant categories (e.g., Programming Languages, Cloud Platforms, Tools, Soft Skills) for readability.
3. **Specificity**: Be specific with skill names (e.g., "Python" instead of "Programming").
4. **Removal**: Remove any skills that are outdated, irrelevant to the target role, or not present in the job description.
5. **Order**: Within categories, consider ordering skills by proficiency or relevance to the job.
</instructions>

<current_skills>
This is the current skills section from the candidate's resume:
{skills}
</current_skills>

<example_of_good_resume_text>
**Technical Skills:**
- Programming Languages: Python, Java, C++, JavaScript, Go
- Cloud Platforms: AWS (EC2, S3, Lambda), Azure, Google Cloud Platform
- Databases: PostgreSQL, MongoDB, MySQL, Redis
- Web Frameworks: Django, Flask, React, Angular, Node.js
- Tools & Technologies: Docker, Kubernetes, Git, Jenkins, RESTful APIs, Microservices

**Soft Skills:**
- Problem-Solving, Communication, Teamwork, Leadership, Agile Methodologies, Project Management
</example_of_good_resume_text>
"""

COVER_LETTER_PROMPT = """<task>
Create a compelling, concise cover letter that aligns my resume/work information with the job description and company value. Analyze and match my qualifications with the job requirements. Then, create cover letter.
</task>

<instructions>
1. **Personalization**: Address the letter to the hiring manager (if known) or the hiring team. Tailor the opening paragraph to express genuine interest in the specific role and company.
2. **Alignment**: Clearly articulate how the candidate's skills, experiences, and achievements directly align with the job requirements and company culture mentioned in the job description.
3. **Value Proposition**: Emphasize the unique value the candidate can bring to the employer and how they can contribute to the company's success. Focus on quantifiable achievements from the candidate's resume that are most relevant to the value. Elaborate on these achievements to provide context and demonstrate impact. Use a bulleted list for easy readability.
4. **Conciseness**: Keep the entire letter brief (250-300 words maximum) and to the point. Avoid repeating information verbatim from the resume.
5. **Professional Tone**: Maintain a professional and enthusiastic tone throughout the letter.
6. **Call to Action**: Conclude with a clear call to action, expressing eagerness for an interview.
7. **No Placeholders**: Do not include any placeholder brackets like [Hiring Manager Name] or [Company Address].
</instructions>

<job_description>
{job_description}
</job_description>

<my_work_information>
{adapted_resume}
</my_work_information>
"""