from typing import Optional
from pydantic import BaseModel, Field

class JobDescription(BaseModel):
    title: str = Field(description="The title of the job.")
    purpose: str = Field(description="A high level overview of the role, and why it exists within the organization.")
    company_name: str = Field(description="The name of the company.")
    location: Optional[str] = Field(default=None, description="The location of the job. For example, 'New York', 'Los Angeles'")
    keywords: list[str] = Field(description="Keywords related to the job. These keywords correspond to skills, key expertise and behavior traits that are desired by the company.")
    responsibilities: list[str] = Field(description="A list of responsibilities associated with the job. These responsibilities can include tasks, duties, and activities that are expected to be performed by the employee. Focus on the essential functions, level of responsibility, areas of accountability, and any supervisory responsibilities.")
    required_qualifications: list[str] = Field(description="A list of necessary requirements for the job. These requirements include minimum experience, education, specific knowledge, skills, abilities, certifications and qualifications that are necessary for the position.")
    desired_qualifications: list[str] = Field(description="A list of qualifications desired by the company that are considered \"nice-to-have\". These qualifications will help to set a candidate apart from the rest.")
    company_description: str = Field(description="A description of the company, including information about the company's mission, values, history, and culture. This information is useful to tailor a resume or cover letter to the company's culture.")
    compliance_text: Optional[str] = Field(default=None, description="Text that is added into a job description primarily for compliance reasons. This includes things related to \"equal opportunity employment\" and \"non-discrimination policies.\"")
    miscellaneous: Optional[str] = Field(default=None, description="Additional notes or comments that may be relevant to the job posting that has not been covered in the previous fields.")
