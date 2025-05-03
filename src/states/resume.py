from typing import Optional
from pydantic import BaseModel, Field

class BasicInfo(BaseModel):
    name: str = Field(description="The name of the person.")
    one_liner: Optional[str] = Field(description="A one-liner description of the person's work or interests.")
    email: Optional[str] = Field(description="The email address of the person.", examples=['example@example.com'])
    phone_number: Optional[str] = Field(description="The phone number of the person.", examples=['123-456-7890','+65 1234 5678'])
    summary: Optional[str] = Field(description="A brief summary of the person's work or interests.")
    links: Optional[dict] = Field(description="A dictionary containing links to social media profiles or other relevant information.", examples=[{'LinkedIn': 'https://www.linkedin.com/in/example', 'GitHub': 'https://github.com/example', 'Medium': 'https://medium.com/example'}])
    residence_status: Optional[str] = Field(description="The residence status of the person. This can be nationality, visa status etc.", examples=['U.S. Citizen', 'U.S. Green Card', 'Permanent Resident'])

class Experience(BaseModel):
    title: str = Field(description="The title of the job role.")
    company: str = Field(description="The name of the company.")
    location: str = Field(description="The location of the company.")
    start: str = Field(description="The start date of the job, in %B %Y format.", examples=['June 2021', 'December 2023'])
    end: str = Field(description="The end date of the job, in %B %Y format. If still in current position, reply with 'Present'", examples=['Present', 'May 2024'])
    descriptions: list[str] = Field(description="A list of points describing the responsibilities and achievements while in the job role.", min_items=1)
    other_info: Optional[str] = Field(description="Any additional information about the experience, such as any relevant skills or accomplishments.")

class Education(BaseModel):
    degree: str = Field(description="The degree obtained.")
    school: str = Field(description="The name of the institution where the degree was obtained.")
    start: str = Field(description="The start date of the education, in %B %Y format.", examples=['June 2019', 'December 2023'])
    end: str = Field(description="The end date of the education, in %B %Y format. If still undergoing studies, reply with 'Present'", examples=['Present', 'May 2024'])
    gpa: Optional[float] = Field(description="The grade point average (GPA) obtained during the education.", min=0., max=5.)
    descriptions: list[str] = Field(description="A list of information about the education, such as achievements.")
    courses: Optional[list[str]] = Field(description="A list of courses taken during the education.")

class Project(BaseModel):
    title: str = Field(description="The name of the project.")
    description: str = Field(description="A brief description of the project.")
    link: Optional[str] = Field(description="A link to the project, if available.", examples=['https://github.com/user/project'])
    technologies: Optional[list[str]] = Field(description="A list of technologies used in the project.")

class Award(BaseModel):
    name: str = Field(description="The name of the award.")
    description: str = Field(description="A brief description of the award.")

class Publication(BaseModel):
    title: str = Field(description="The title of the publication.")
    description: str = Field(description="A brief description of the publication.")
    link: Optional[str] = Field(description="A link to the publication, if available.", examples=['https://www.jstor.org/stable/1234'])
    authors: Optional[list[str]] = Field(description="A list of authors of the publication.")

class Language(BaseModel):
    name: str = Field(description="The name of the language.")
    proficiency_level: Optional[str] = Field(description="The proficiency level of the language.", examples=['Native', 'Fluent', 'Limited'])

class SkillSet(BaseModel):
    name: str = Field(description="The name of the group of skills. If one is not provided, provide one based on the skills.", examples=['Technical Skills', 'Soft Skills', 'Project Management'])
    skills: list[str] = Field(description="A list of skills within the group.")

class Resume(BaseModel):
    basic_info: BasicInfo = Field(description="Personal information such as name, email, phone number.")
    experience: list[Experience] = Field(description="Professional experience including job title, company, location, and duration.")
    education: list[Education] = Field(description="Educational background including degree, school, and graduation year.")
    projects: list[Project] = Field(description="Projects completed by the individual.")
    awards: Optional[list[Award]] = Field(description="Awards received by the individual.")
    publications: Optional[list[Publication]] = Field(description="Publications written by the individual.")
    skills: list[SkillSet] = Field(description="A list of skill sets within the resume.")
    languages: Optional[list[Language]] = Field(description="Languages spoken by the individual.")

