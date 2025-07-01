from pydantic import BaseModel, Field

class CoverLetter(BaseModel):
    company_name: str = Field(description="The name of the company the cover letter is addressed to.")
    team_name: str = Field(description="The name of the team or department the cover letter is for.")
    position_title: str = Field(description="The title of the position the cover letter is for.")
    salutation: str = Field(description="The salutation used in the cover letter, typically 'Dear [Hiring Manager]'.")
    body: str = Field(description="The main body of the cover letter, including salutation and closing.")
    closing: str = Field(description="The closing statement of the cover letter, typically 'Sincerely' or 'Best regards'.")

    def __str__(self) -> str:
        return (
            f"# {self.company_name}\n"
            f"**Team:** {self.team_name}\n"
            f"**Position:** {self.position_title}\n\n"
            f"{self.salutation}\n\n"
            f"{self.body}\n\n"
            f"{self.closing},\n"
        )