import yaml
from src.states.resume import Resume 
from typing import Dict, Any, List
import logging
import tempfile
import subprocess
import os

logger = logging.getLogger(__name__)

def export_resume_to_pdf(resume: Resume, keywords: list[str] | None = None, rendercv_config: dict = None):
    """
    Exports a Resume object to a PDF file following the RenderCV structure.

    Args:
        resume (Resume): An object containing the processed resume data
        keywords (list[str] | None, optional): A list of keywords to bold in the resume. Defaults to None.
        rendercv_design (dict): rendercv design and settings. If None, uses default design.
    """
    cv_content: Dict[str, Any] = {}

    # Basic Info
    cv_content["name"] = resume.basic_info.name
    cv_content["email"] = resume.basic_info.email
    cv_content["phone"] = resume.basic_info.phone_number
    if resume.basic_info.residence_status:
        cv_content["location"] = resume.basic_info.residence_status
    
    social_networks = []
    if resume.basic_info.links:
        for link_str in resume.basic_info.links:
            network_name = "Website"
            url = link_str.strip()
            if ":" in link_str:
                parts = link_str.split(":", 1)
                network_name = parts[0].strip()
                url = parts[1].strip()

            display_text = network_name if network_name != "Website" else url

            if network_name.lower() in ["linkedin", "github", "gitlab", "instagram", "orcid", "stack overflow", "google scholar"]:
                # Extract the part of the URL after the last '/'
                formatted_url = url.rstrip('/').split('/')[-1]
            else:
                logger.warning(f'Could not identify link {link_str} as one of the common ones! Trying our best...')
                formatted_url = f"[{display_text}]({url})"
            social_networks.append({"network": network_name, "username": formatted_url})
    if social_networks:
        cv_content["social_networks"] = social_networks

    # Sections
    sections: Dict[str, List[Dict[str, Any]]] = {}

    # Summary
    sections[''] = [resume.basic_info.summary]

    # Experience
    if resume.experience and resume.experience.experience:
        experience_entries = []
        for exp in resume.experience.experience:
            entry = {
                "company": exp.company,
                "position": exp.title,
                "start_date": exp.start,
                "end_date": exp.end if exp.end != "Present" else "present",
                "highlights": exp.descriptions,
            }
            if exp.location: entry["location"] = exp.location
            if exp.other_info: entry["summary"] = exp.other_info
            experience_entries.append(entry)
        sections["Experience"] = experience_entries

    # Education
    if resume.education and resume.education.education:
        education_entries = []
        for edu in resume.education.education:
            entry = {
                "institution": edu.school,
                "area": edu.area,
                "degree": edu.degree,
                "location": edu.location,
                "start_date": edu.start,
                "end_date": edu.end if edu.end != "Present" else "present",
                "highlights": edu.descriptions,
            }
            if edu.gpa:
                entry["summary"] = f"GPA: {edu.gpa}" # Adding GPA to summary
            education_entries.append(entry)
        sections["Education"] = education_entries

    # Projects
    if resume.projects and resume.projects.projects:
        project_entries = []
        for proj in resume.projects.projects:
            highlights = proj.highlights if proj.highlights else []
            
            entry = {
                "name": f"[{proj.title}]({proj.link})" if proj.link else proj.title,
                "summary": proj.description
            }
            if highlights: entry["highlights"] = highlights
            project_entries.append(entry)
        sections["Projects"] = project_entries

    # Publications
    if resume.publications and resume.publications.publications:
        publication_entries = []
        for pub in resume.publications.publications:
            entry = {
                "title": f'[{pub.title}]({pub.link})' if pub.link else pub.title,
                "authors": pub.authors,
                "date": pub.date,
                "journal": pub.journal_name
            }
            if pub.description: entry["summary"] = pub.description
            publication_entries.append(entry)
        sections["Publications"] = publication_entries

    # Awards
    if resume.awards:
        award_entries = []
        for award in resume.awards:
            if ':' in award:
                label, details = award.split(':', 1)
                award_entries.append({
                    "label": label.strip(),
                    "details": details.strip()
                })
            else:
                award_entries.append(award.strip())
        sections["Awards"] = award_entries
    
    # Skills
    if resume.skills and resume.skills.skills:
        skill_entries = []
        for skill in resume.skills.skills:
            if ':' in skill:
                label, details = skill.split(':', 1)
                skill_entries.append({
                    "label": label.strip(),
                    "details": details.strip()
                })
            else:
                skill_entries.append(skill.strip())
        sections["Skills"] = skill_entries

    # Certifications
    if resume.certifications:
        sections["Certifications"] = [{"bullet": cert} for cert in resume.certifications]

    # Languages
    if resume.languages:
        languages = []
        for lang in resume.languages:
            if ':' in lang:
                proficiency, langs = lang.split(':', 1)
                languages.append(f'**{proficiency}**: {langs}')
            else:
                languages.append(lang)
        sections["Languages"] = [('\u00A0'*15).join(resume.languages)]

    if sections:
        cv_content["sections"] = sections

    if keywords:
        if "rendercv_settings" not in rendercv_config:
            rendercv_config["rendercv_settings"] = {}
        rendercv_config["rendercv_settings"]["bold_keywords"] = keywords

    rendercv_config.update({"cv": cv_content})
    # Create a temporary YAML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp_file:
        yaml.dump(rendercv_config, tmp_file, sort_keys=False, default_flow_style=False)
        tmp_yaml_path = tmp_file.name

    try:
        # Run the rendercv command
        subprocess.run(
            ["rendercv", "render", tmp_yaml_path],
            check=True
        )
    finally:
        # Clean up the temporary file
        os.remove(tmp_yaml_path)
    return
