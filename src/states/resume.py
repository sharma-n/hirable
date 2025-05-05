from typing import Optional
from pydantic import BaseModel, Field, computed_field
import logging

from src.utils.parse import parse_file


logger = logging.getLogger(__name__)

class BasicInfo(BaseModel):
    name: str = Field(description="The name of the person.")
    one_liner: Optional[str] = Field(default=None, description="A one-liner description of the person's work or interests.")
    email: str = Field(description="The email address of the person. For example, id@provider.com")
    phone_number: str = Field(description="The phone number of the person. Include the country code if provided.")
    summary: Optional[str] = Field(default=None, description="A brief summary of the person's work or interests.")
    links: Optional[dict] = Field(default=None, description="A dictionary containing links to social media profiles or other relevant information. For example, {'LinkedIn': 'https://www.linkedin.com/in/example', 'GitHub': 'https://github.com/example', 'Medium': 'https://medium.com/example'}")
    residence_status: Optional[str] = Field(default=None, description="The residence status of the person. This can be nationality, visa status etc.", examples=['U.S. Citizen', 'U.S. Green Card', 'Permanent Resident'])

    def __str__(self):
        return f"## Basic Information\n- Name: {self.name}\n"\
            + ("" if self.one_liner is None else f"- One liner description: {self.one_liner}")\
            + f"- Email: {self.email}\n"\
            + f"- Phone number: {self.phone_number}\n"\
            + ("" if self.summary is None else f"- Summary: {self.summary}\n")\
            + ("" if self.residence_status is None else f"- Residence status: {self.residence_status}\n")\
            + ("" if self.links is None else f"- Links: {', '.join([f'{k}: {v}' for k, v in self.links.items()])}\n") + "\n"

class Experience(BaseModel):
    title: str = Field(description="The title of the job role.")
    company: str = Field(description="The name of the company.")
    location: str = Field(description="The location of the company.")
    start: str = Field(description="The start date of the job, in %B %Y format, for example July 2023.")
    end: str = Field(description="The end date of the job, in %B %Y format, for example July 2023. If still in current position, reply with 'Present'")
    descriptions: list[str] = Field(description="A list of points describing the responsibilities and achievements while in the job role.", min_items=1)
    other_info: Optional[str] = Field(description="Any additional information about the experience, such as any relevant skills or accomplishments.")

    def __str__(self):
        return f"### {self.title} at {self.company}, {self.location}\n from {self.start} to {self.end}\n"\
            + f"Responsibilities and Achievements:\n- " + "\n- ".join(self.descriptions) + "\n\n"\
            + ("" if self.other_info is None else f"Other Information:\n{self.other_info}") + "\n"

class Education(BaseModel):
    degree: str = Field(description="The degree obtained.")
    school: str = Field(description="The name of the institution where the degree was obtained.")
    start: str = Field(description="The start date of the education, in %B %Y format, for example July 2023.")
    end: str = Field(description="The end date of the education, in %B %Y format, for example July 2023. If still undergoing studies, reply with 'Present'")
    gpa: Optional[str] = Field(default=None, description="The grade point average (GPA) obtained during the education, for example '3.8' or '4.0/5.0'.")
    descriptions: list[str] = Field(description="A list of information about the education, such as achievements.")
    courses: Optional[list[str]] = Field(default=None, description="A list of courses taken during the education.")

    def __str__(self):
        return f"### {self.degree} from {self.school} ({self.start} - {self.end})\n- "\
            + '\n- '.join(self.descriptions) + "\n"\
            + ("" if self.gpa is None else f"- GPA: {self.gpa}\n")\
            + ("" if self.courses is None else f"- Courses: {', '.join(self.courses)}\n")

class Project(BaseModel):
    title: str = Field(description="The name of the project.")
    description: str = Field(description="A brief description of the project.")
    link: Optional[str] = Field(default=None, description="A link to the project, if available. For example, https://github.com/user/project")
    technologies: Optional[list[str]] = Field(default=None, description="A list of technologies used in the project.")

    def __str__(self):
        return f"### {self.title}\n- "\
            + '\n- '.join(self.description.split('\n')) + "\n"\
            + ("" if self.link is None else f"- Link: {self.link}\n")\
            + ("" if self.technologies is None else f"- Technologies Used: {', '.join(self.technologies)}\n")

class Publication(BaseModel):
    title: str = Field(description="The title of the publication.")
    authors: list[str] = Field(description="A list of authors of the publication.")
    description: Optional[str] = Field(default=None, description="A brief description of the publication.")
    link: Optional[str] = Field(default=None, description="A link to the publication, if available.")
    
    def __str__(self):
        return f"- {self.title} by {', '.join(self.authors)}" + ("" if self.description is None else f": {self.description}.") + ("" if self.link is None else f" Link: {self.link}") + "\n"

class InputFile(BaseModel):
    filepath: str = Field(description="The path to the input resume file.")

    @computed_field
    @property
    def resume_text(self) -> str:
        return parse_file(self.filepath)

class Resume(BaseModel):
    basic_info: BasicInfo = Field(description="Personal information such as name, email, phone number.")
    experience: list[Experience] = Field(description="Professional experience including job title, company, location, and duration.")
    education: list[Education] = Field(description="Educational background including degree, school, and graduation year.")
    projects: list[Project] = Field(description="Projects completed by the individual.")
    publications: Optional[list[Publication]] = Field(default=None, description="Publications written by the individual.")
    awards: Optional[list[str]] = Field(default=None, description="Awards received by the individual. Each award should be listed with its description if provided..")
    certifications: Optional[list[str]] = Field(default=None, description="Certifications obtained by the individual. Each certification should be listed with its description if provided.")
    languages: Optional[list[str]] = Field(default=None, description="Languages spoken by the individual. Each language should be listed the proficiency level if provided.")
    skills: list[dict] = Field(description="A dictionary where each key is a group name and values are the skills within that group. If groups are not provided for the skills, then group them based on types (e.g., programming, design, etc.).")
    other_info: Optional[str] = Field(default=None, description="Additional information from the resume that is not captured in the previous fields. You should group similar information together under a heading and the write each piece of information as a bullet point.")

    def __str__(self):
        return "# Resume\n"\
            + str(self.basic_info)\
            + "## Work Experience\n" + '\n'.join(self.experience)\
            + "## Education\n" + '\n'.join(self.education)\
            + "## Projects\n" + '\n'.join(self.projects)\
            + ("" if self.publications is None else "## Publications\n- " + '\n- '.join(self.publications) + "\n")\
            + ("" if self.awards is None else "## Awards\n- " + '\n- '.join(self.awards) + "\n")\
            + ("" if self.certifications is None else "## Certifications\n- " + '\n- '.join(self.certifications) + "\n")\
            + ("" if self.languages is None else "## Languages\n- " + '\n- '.join(self.languages) + "\n")\
            + "## Skills\n- " + '\n- '.join([f"{k}: {v}" for k, v in self.skills.items()]) + "\n"\
            + ("" if self.other_info is None else f"## Other Information\n{self.other_info}") + "\n"\

class FullState(InputFile, Resume):
    pass