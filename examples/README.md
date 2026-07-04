# Sample CVs for hirable testing

This folder contains 4 realistic, richly-populated sample resumes (both YAML source and compiled PDF) for manual end-to-end testing of the hirable application.

## Files

- **computer_engineer.yaml / computer_engineer.pdf** — Senior Embedded Systems Engineer with firmware, RTOS, and low-level optimization focus. Edge case: ongoing role with `end_date: present`.
- **data_scientist.yaml / data_scientist.pdf** — Senior Data Scientist specializing in A/B testing and causal inference. Edge case: free-form `date` string instead of start/end date pairs.
- **mle_engineer.yaml / mle_engineer.pdf** — Staff ML Engineer with infrastructure and production systems focus. Edge case: less-common social network (StackOverflow with user_id/username format).
- **ai_researcher.yaml / ai_researcher.pdf** — AI Research Scientist with publications section, PhD-level experience. Edge case: publications listed as PublicationEntry.

## Usage

Each PDF can be uploaded directly into hirable via the resume upload flow:
1. Sign up a new account.
2. Navigate to the Profile page.
3. Upload one of the PDF files.
4. The app's parser (docling + LLM structured extraction) will parse the resume into a master profile.
5. Review and edit the parsed profile in the Profile editor.
6. Use the agent panel to enrich the profile with clarifying questions.
7. Test CV generation against sample jobs and edit the tailored YAML output.

## Regenerating PDFs

If you modify any `.yaml` file and want to recompile the PDFs, run:
```bash
cd backend && uv run python ../examples/render_pdfs.py
```

This uses the same RenderCV/Typst compilation pipeline the app itself uses, ensuring consistency between example output and production output.

## YAML Schema Reference

All YAML files follow RenderCV v2.8 schema. Key sections:
- **cv.name, headline, location, email, phone, website, social_networks** — Contact info.
- **cv.sections.summary** — TextEntry (free-form paragraph).
- **cv.sections.experience** — ExperienceEntry (company, position, dates, highlights).
- **cv.sections.projects** — NormalEntry (name, summary, highlights).
- **cv.sections.education** — EducationEntry (institution, area, degree, highlights).
- **cv.sections.skills** — OneLineEntry (label + details).
- **cv.sections.publications** — PublicationEntry (title, authors, journal, date).
- **design.theme** — Set to `engineeringresumes` (matches app's `config.yaml` default).

See [../docs/rendercv.md](../docs/rendercv.md) for the full schema documentation.
