from pathlib import Path
import streamlit as st
import asyncio
import re
import os
import base64
import yaml

from src.graph import get_graph
from src.states import InputState
from src.states.resume import Resume
from src.utils.parse import parse_file
from src.utils.export import export_resume_to_pdf
from src.utils import setup_logging

setup_logging()

st.set_page_config(layout="wide")
st.title("Hirable: AI-Powered Resume & Cover Letter Tailoring")

st.write("Upload your resume and paste a job description to get a tailored resume and cover letter.")

# Job Description Input
st.header("1. Job Description")
job_desc_input_method = st.radio("Choose Job Description Input Method", ("URL", "Text"), horizontal=True, label_visibility='collapsed')

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
resume_file = st.file_uploader("Upload Resume (PDF, DOCX, TXT, TEX, YAML)", type=["pdf", "docx", "txt", "tex", "yaml"])

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

            # Store the generated resume in the session state
            st.session_state.resume_out = output['resume_out']
            st.session_state.job = output['job']
            st.session_state.cover_letter = output['cover_letter']
            st.session_state.show_results = True
            st.rerun()

if 'show_results' in st.session_state and st.session_state.show_results:
    st.subheader("Tailored Resume (RenderCV YAML)")

    # Initialize the edited_yaml in session_state if it's not there
    if 'edited_yaml' not in st.session_state:
        st.session_state.edited_yaml = yaml.dump(st.session_state.resume_out.model_dump(), sort_keys=False, default_flow_style=False)

    with st.expander("View and Edit Resume YAML"):
        # Display the YAML in a text area for editing
        st.session_state.edited_yaml = st.text_area(
            "RenderCV YAML",
            value=st.session_state.edited_yaml,
            height=400
        )

    if st.button("Generate PDF from YAML"):
        try:
            # Parse the edited YAML
            edited_resume_data = yaml.safe_load(st.session_state.edited_yaml)
            resume_for_pdf = Resume(**edited_resume_data)

            # Export resume to PDF
            rendercv_config_path = 'src/config/rendercv_config.yaml'
            rendercv_config = yaml.safe_load(open(rendercv_config_path, 'r'))
            
            with st.spinner("Generating PDF..."):
                export_resume_to_pdf(resume_for_pdf, keywords=st.session_state.job.keywords, rendercv_config=rendercv_config)

            # Display PDF
            st.subheader("Tailored Resume PDF")
            resume_name = resume_for_pdf.basic_info.name
            pdf_file_name = f"{resume_name.replace(' ', '_')}_CV.pdf"
            pdf_path = os.path.join("data", "rendercv_output", pdf_file_name)

            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="1000" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
            else:
                st.error(f"Could not find the generated PDF at {pdf_path}")

        except (yaml.YAMLError, TypeError, AttributeError) as e:
            st.error(f"Error parsing YAML or generating PDF: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

    # Display Cover Letter
    st.subheader("Generated Cover Letter")
    st.markdown(st.session_state.cover_letter)

    # Add download button for the parsed resume
    st.download_button(
        label="Download Parsed Resume (YAML)",
        data=st.session_state.edited_yaml,
        file_name="parsed_resume.yaml",
    )