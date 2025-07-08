# Hirable: Your Personal AI Resume Tailor

Hirable takes your resume and a job description, and crafts a tailored resume and cover letter designed to catch the eye of recruiters and hiring managers.

## Features

- **AI-Powered Resume Adaptation:** Large Language Models (LLMs) are used to analyze your resume and a job description, then rewrites your resume to highlight the skills and experiences that are most relevant to the job.
- **Custom Cover Letter Generation:** Say goodbye to writer's block. Hirable generates a personalized cover letter that complements your tailored resume and speaks directly to the needs of the employer.
- **Multiple Input Formats:** Upload your resume as a PDF, DOCX, TXT, or even a TEX file. Provide the job description as a URL or paste the raw text.
- **Interactive Web Interface:** A user-friendly web interface built with Streamlit makes it easy to upload your documents, view the results, and even edit the generated resume YAML before exporting.
- **Professional PDF Export:** Generate a professional-looking PDF of your tailored resume using the `rendercv` library.

## How It Works

Hirable uses a structured pipeline to process your documents and generate tailored results:

1.  **Ingestion:** The application ingests your resume and the job description, parsing them into structured data formats using Pydantic models.
2.  **Adaptation:** Using a series of prompts and the power of LangChain and LangGraph, Hirable carefully adapts each section of your resume—from your summary to your skills—to align with the job description.
3.  **Generation:** A custom cover letter is generated based on your newly tailored resume and the job description.
4.  **Export:** The final resume is converted into a professional PDF format using `rendercv`.

The entire workflow is orchestrated as a state graph using LangGraph, ensuring a logical and efficient flow of data.

## Getting Started
### Installation

1.  We use `uv` for dependency management. Install the dependencies:

    ```bash
    # If you already have uv, no need to run the curl command
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv sync
    ```
2. For whatever reason, `rendercv` has very strict package requirements that make `uv` go crazy. So just install it manually with 
    ```bash
    uv pip install "rendercv[full]"
    ```
3. Ensure that you have your OpenAI, Gemini, Anthropic or whatever key setup as an environment variable. Change `src/config/__init__.py` to adjust the model / model provider you want to use.
### Running the Application
To start the interactive web application, run:

```bash
streamlit run streamlit_app.py
```

This will open the Hirable interface in your web browser. From there, you can upload your resume, provide a job description, and generate your tailored documents.

For command-line usage, you can run the main script:

```bash
uv run main.py
```

## Future Work

Hirable is under active development. Here are some of the features we'd like to work on:

- [ ] **Enhanced UI/UX:** A more polished and interactive user interface.
- [ ] **Batch Processing:** The ability to tailor your resume for multiple job descriptions at once.

We welcome contributions! If you have an idea for a new feature or have found a bug, please open an issue or submit a pull request.