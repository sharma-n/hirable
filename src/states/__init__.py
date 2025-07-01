import logging
from typing import Optional
from pydantic import BaseModel, Field, model_validator, computed_field

from src.states.job_desc import JobDescription
from src.states.resume import Resume
from src.states.cover_letter import CoverLetter
from src.utils.parse import parse_url

logger = logging.getLogger(__name__)

class InputState(BaseModel):
    job_url: Optional[str] = Field(default=None, description="The URL to the job posting.")
    job_desc_raw: Optional[str] = Field(default=None, description="The raw text of the job description.")
    resume_raw: Optional[str] = Field(default=None, description="The raw text of the resume.")
    resume_yaml: Optional[dict] = Field(default=None, description="A YAML dict containing a parsed resume.")

    @model_validator(mode='after')
    def validate_input(self):
        if self.job_url is None and self.job_desc_raw is None:
            raise ValueError("At least one of job_desc_raw or url must be provided.")
        elif self.job_desc_raw is not None:
            logger.info(f"Job description is provided via raw text. Using it directly (URL will be ignored if provided).")
        else:
            logger.info(f"Job URL is provided. Parsing it to extract job description.")
            self.job_desc_raw = parse_url(self.job_url)

        if self.resume_raw is None and self.resume_yaml is None:
            raise ValueError("At least one of resume_raw or resume_yaml must be provided.")
        elif self.resume_raw is not None and self.resume_yaml is not None:
            logger.warning("Both resume_raw and resume_yaml are provided. Using resume_raw and ignoring resume_yaml. Will re-parse the resume, using an LLM.")
            self.resume_yaml = None
        return self
    
class OutputState(BaseModel):
    resume: Resume = Field(description="The original parsed resume object.")
    job: JobDescription = Field(description="The parsed job description object.")
    resume_out: Optional[Resume] = Field(default=None, description="The adapted resume object.")
    cover_letter: Optional[CoverLetter] = Field(default=None, description="The generated cover letter.")

class FullState(InputState, OutputState):
    pass