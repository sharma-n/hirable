
from pathlib import Path
import streamlit as st
import asyncio
import re

import yaml

from src.graph import get_graph
from src.states import InputState
from src.utils.parse import parse_file
from src.utils.utils import setup_logging

setup_logging()

st.set_page_config(layout="wide")
st.title("Hirable: AI-Powered Resume & Cover Letter Tailoring")

st.write("Upload your resume and paste a job description to get a tailored resume and cover letter.")

# Job Description Input
st.header("1. Job Description")
job_desc_input_method = st.radio("Choose Job Description Input Method", ("URL", "Text"))

job_description_url = None
job_description_input = None

if job_desc_input_method == "URL":
    job_description_url = st.text_input("Paste Job Description URL here", help="Enter the URL of the job posting.")
    if job_description_url:
        # Basic URL validation using regex
        url_regex = re.compile(
            r'^(?:http|ftp)s?://' # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
            r'localhost|' # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
            r'(?::\d+)?' # optional port
            r'(?:/?|[/?]\S+)', re.IGNORECASE)
        if not url_regex.match(job_description_url):
            st.error("Please enter a valid URL.")
            job_description_url = None # Invalidate the URL if it's not valid
else:
    job_description_input = st.text_area("Paste Job Description Text here", height=300, help="Copy and paste the full job description text.")

# Resume Upload
st.header("2. Upload Your Resume")
resume_file = st.file_uploader("Upload Resume (PDF, DOCX, TXT, YAML)", type=["pdf", "docx", "txt", "yaml"])

# Process Button
st.header("3. Generate Tailored Documents")
if st.button("Generate Tailored Resume & Cover Letter"):
    if not resume_file:
        st.warning("Please upload your resume.")
    elif not job_description_url and not job_description_input:
        st.warning("Please provide either a job description URL or paste the job description text.")
    else:
        with st.spinner("Processing your documents... This may take a moment."):
            resume_input_args = {}
            if resume_file:
                if Path(resume_file.name).suffix.lower()=='.yaml':
                    resume_input_args['resume_yaml'] = yaml.safe_load(resume_file.getvalue())
                else:
                    resume_input_args['resume_raw'] = parse_file(resume_file)

                if job_desc_input_method == "URL":
                    resume_input_args['job_url'] = job_description_url
                else:
                    resume_input_args['job_desc_raw'] = job_description_input

            # Initialize graph and run
            graph = get_graph()
            state = InputState(**resume_input_args)
            output = asyncio.run(graph.ainvoke(input=state))

            st.success("Documents processed successfully!")

            st.subheader("Tailored Resume")
            st.markdown(output['resume_out'])

            st.subheader("Generated Cover Letter")
            st.markdown(output['cover_letter'])

            # Add download button for the parsed resume (output['resume'])
            st.download_button(
                label="Download Parsed Resume (YAML)",
                data=yaml.dump(output['resume'].model_dump(), sort_keys=False),
                file_name="parsed_resume.yaml",
            )