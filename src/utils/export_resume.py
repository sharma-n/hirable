import yaml
from src.states.resume import Resume 
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

def export_to_yaml(resume: Resume, file_path: str):
    """
    Exports a Resume object to a YAML file following the RenderCV structure.
    """
    cv_content: Dict[str, Any] = {}

    # Basic Info
    cv_content["name"] = resume.basic_info.name
    if resume.basic_info.one_liner:
        cv_content["summary"] = resume.basic_info.one_liner # Mapping one_liner to summary in RenderCV
    cv_content["email"] = resume.basic_info.email
    cv_content["phone"] = resume.basic_info.phone_number
    
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

    # Experience
    if resume.experience and resume.experience.experience:
        experience_entries = []
        for exp in resume.experience.experience:
            entry = {
                "company": exp.company,
                "position": exp.title,
                "location": exp.location,
                "start_date": exp.start,
                "end_date": exp.end if exp.end != "Present" else "present",
                "highlights": exp.descriptions,
            }
            if exp.other_info:
                entry["summary"] = exp.other_info
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
            if edu.courses:
                if "summary" in entry:
                    entry["summary"] += f"\nCourses: {', '.join(edu.courses)}"
                else:
                    entry["summary"] = f"Courses: {', '.join(edu.courses)}"
            education_entries.append(entry)
        sections["Education"] = education_entries

    # Projects
    if resume.projects and resume.projects.projects:
        project_entries = []
        for proj in resume.projects.projects:
            highlights = proj.highlights if proj.highlights else []
            if proj.technologies:
                highlights.append(f"Technologies: {', '.join(proj.technologies)}")
            
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
                "title": f"[{pub.title}]({pub.link})" if pub.link else pub.title,
                "authors": pub.authors,
            }
            if pub.description:
                entry["summary"] = pub.description
            publication_entries.append(entry)
        sections["Publications"] = publication_entries

    # Skills
    if resume.skills and resume.skills.skills:
        sections["Skills"] = [{"bullet": skill} for skill in resume.skills.skills]

    # Awards
    if resume.awards:
        sections["Awards"] = [{"bullet": award} for award in resume.awards]

    # Certifications
    if resume.certifications:
        sections["Certifications"] = [{"bullet": cert} for cert in resume.certifications]

    # Languages
    if resume.languages:
        sections["Languages"] = [{"bullet": lang} for lang in resume.languages]

    # Other Info
    if resume.other_info:
        sections["Other Information"] = [{"text": resume.other_info}]

    if sections:
        cv_content["sections"] = sections

    design_content = {
        'theme': 'sb2nov'
    }
    full_yaml_content = {"cv": cv_content, "design": design_content}

    with open(file_path, "w") as f:
        yaml.dump(full_yaml_content, f, sort_keys=False, default_flow_style=False)

