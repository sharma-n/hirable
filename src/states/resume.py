from typing import Optional
from pydantic import BaseModel, Field

class BasicInfo(BaseModel):
    name: str = Field(description="The name of the person.")
    email: str = Field(description="The email address of the person. For example, id@provider.com")
    phone_number: str = Field(description="The phone number of the person. Include the country code if provided.")
    summary: Optional[str] = Field(default=None, description="A brief summary of the person's work or interests.")
    links: Optional[list[str]] = Field(default=None, description="A list containing links to social media profiles. Each link should include the name of the platform and the URL separated by a colon(:). For example, ['LinkedIn: https://www.linkedin.com/in/example', 'GitHub: https://github.com/example', 'Medium: https://medium.com/example']")
    residence_status: Optional[str] = Field(default=None, description="The residence status of the person. This can be nationality, visa status etc. For example, 'U.S. Citizen', 'U.S. Green Card', 'Permanent Resident'")

    def __str__(self):
        return f"## Basic Information\n- Name: {self.name}\n"\
            + f"- Email: {self.email}\n"\
            + f"- Phone number: {self.phone_number}\n"\
            + ("" if self.summary is None else f"- Summary: {self.summary}\n")\
            + ("" if self.residence_status is None else f"- Residence status: {self.residence_status}\n")\
            + ("" if self.links is None else f"- Links: {', '.join(self.links)}\n") + "\n"

class Experiences(BaseModel):
    class Experience(BaseModel):
        title: str = Field(description="The title of the job role.")
        company: str = Field(description="The name of the company.")
        start: str = Field(description="The start date of the job, in YYYY-MM-DD or YYYY-MM format, for example 2023-05.")
        end: str = Field(description="The end date of the job, in YYYY-MM-DD or YYYY-MM format, for example 2023-05. If still in current position, reply with 'present'")
        location: Optional[str] = Field(description="The location of the company.")
        descriptions: list[str] = Field(description="A list of points describing the responsibilities and achievements while in the job role.")
        other_info: Optional[str] = Field(description="Any additional information about the experience, such as any relevant skills or accomplishments.")

        def __str__(self):
            return f"### {self.title} at {self.company}, {self.location} from {self.start} to {self.end}\n"\
                + f"Responsibilities and Achievements:\n- " + "\n- ".join(self.descriptions) + "\n"\
                + ("" if self.other_info is None else f"\nOther Information:\n{self.other_info}") + "\n"

    experience: list[Experience] = Field(description="Professional experience including job title, company, location, and duration.")

    def __str__(self):
        return '\n'.join([str(e) for e in self.experience]) + "\n"
class Educations(BaseModel):
    class Education(BaseModel):
        degree: str = Field(description="The degree obtained, for example B.Eng., M.Eng etc. Does not include the field of study.")
        area: str = Field(description="The area or field of study, for example Electrical Engineering, Economics, Medicine etc.")
        school: str = Field(description="The name of the institution where the degree was obtained.")
        start: str = Field(description="The start date of the education, in YYYY-MM-DD or YYYY-MM format, for example 2023-05.")
        end: str = Field(description="The end date of the education, in YYYY-MM-DD or YYYY-MM format, for example 2025-05. If still undergoing studies, reply with 'present'")
        location: str = Field(description='Country where the school is located.')
        gpa: Optional[str] = Field(default=None, description="The grade point average (GPA) obtained during the education, for example '3.8' or '4.0/5.0'.")
        descriptions: list[str] = Field(description="A list of information about the education, such as achievements.")
        courses: Optional[list[str]] = Field(default=None, description="A list of courses taken during the education.")

        def __str__(self):
            return f"### {self.degree} in {self.area} from {self.school}, {self.location} ({self.start} - {self.end})\n- "\
                + '\n- '.join(self.descriptions) + "\n"\
                + ("" if self.gpa is None else f"- GPA: {self.gpa}\n")\
                + ("" if self.courses is None else f"- Courses: {', '.join(self.courses)}\n")
        
    education: list[Education] = Field(description="Educational background including degree, school, and graduation year.")

    def __str__(self):
        return '\n'.join([str(e) for e in self.education]) + "\n"

class Projects(BaseModel):

    class Project(BaseModel):
        title: str = Field(description="The name of the project.")
        description: str = Field(description="A brief description of the project.")
        highlights: Optional[list[str]] = Field(description="A list of key achievements highlighted about the project.")
        link: Optional[str] = Field(default=None, description="A link to the project, if available. For example, https://github.com/user/project")
        technologies: Optional[list[str]] = Field(default=None, description="A list of technologies used in the project.")

        def __str__(self):
            return f"### {self.title}\n- "\
                + '\n- '.join(self.description.split('\n')) + "\n"\
                + ("" if self.link is None else f"- Link: {self.link}\n")\
                + ("" if self.technologies is None else f"- Technologies Used: {', '.join(self.technologies)}\n")

    projects: list[Project] = Field(description="Projects completed by the individual.")

    def __str__(self):
        return '\n'.join([str(p) for p in self.projects]) + "\n"

class Publications(BaseModel):
    class Publication(BaseModel):
        title: str = Field(description="The title of the publication.")
        authors: list[str] = Field(description="A list of authors of the publication.")
        date: str = Field(description="The date of the publication, in YYYY-MM-DD or YYYY-MM format.")
        journal_name: str = Field(description='The name of the journal / conference where the publication was done.')
        description: Optional[str] = Field(default=None, description="A brief description of the publication.")
        link: Optional[str] = Field(default=None, description="A link to the publication, if available.")
        
        def __str__(self):
            return f"- {self.title} by {', '.join(self.authors)} (published on {self.date} at {self.journal_name})" + ("" if self.description is None else f": {self.description}.") + ("" if self.link is None else f" Link: {self.link}") + "\n"

    publications: list[Publication] = Field(description="Publications written by the individual.")

    def __str__(self):
        return '\n'.join([str(p) for p in self.publications]) + "\n"

class Skills(BaseModel):
    skills: list[str] = Field(description="A list of grouped skills that the resume mentions. If groups are not provided for the skills, then group them based on types (e.g., programming, design, etc.). Each element of the list should be in the form of 'Group: comma separated skills in the group'. Make sure you extract less than 4 groups.")

    def __str__(self):
        return '- ' + '\n- '.join(self.skills) + "\n"

class Resume(BaseModel):
    basic_info: BasicInfo = Field(description="Personal information such as name, email, phone number.")
    experience: Experiences = Field(description="A list of professional experiences.")
    education: Educations = Field(description="A list of educational backgrounds.")
    projects: Projects = Field(description="A list of projects.")
    publications: Optional[Publications] = Field(default=None, description="A list of publications.")
    awards: Optional[list[str]] = Field(default=None, description="Awards received by the individual. Each award should be listed as 'Name of Award: Description'")
    certifications: Optional[list[str]] = Field(default=None, description="Certifications obtained by the individual. Each certification should be listed with its description if provided.")
    languages: Optional[list[str]] = Field(default=None, description="Languages spoken by the individual. Should be grouped by proficiency level. If no proficiency is provided, assume Fluent. Example response is ['Fluent: English, Spanish','Intermediate: Japanese']")
    skills: Skills = Field(description="A list of skills.")
    other_info: Optional[str] = Field(default=None, description="Additional information from the resume that is not captured in the previous fields. You should group similar information together under a heading and the write each piece of information as a bullet point.")

    def __str__(self):
        return "# Resume\n"\
            + str(self.basic_info)\
            + "## Work Experience\n" + str(self.experience)\
            + "## Education\n" + str(self.education)\
            + "## Projects\n" + str(self.projects)\
            + ("" if self.publications is None else "## Publications\n" + str(self.publications))\
            + ("" if self.awards is None else "## Awards\n- " + '\n- '.join(self.awards) + "\n\n")\
            + ("" if self.certifications is None else "## Certifications\n- " + '\n- '.join(self.certifications) + "\n")\
            + ("" if self.languages is None else "## Languages\n- " + '\n- '.join(self.languages) + "\n\n")\
            + "## Skills\n" + str(self.skills)\
            + ("" if self.other_info is None else f"## Other Information\n{self.other_info}") + "\n"
