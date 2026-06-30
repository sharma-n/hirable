# good_resume.md — The Resume & Cover Letter Rulebook

> **What this is.** A distilled, prompt-ready rulebook for *generating, tailoring, and critiquing*
> developer resumes (CVs) and cover letters. It is the single source of truth that the agent and all
> generation prompts should cite.
>
> **How to use it.** When building a CV or cover letter, follow these rules top to bottom. When
> critiquing one, run the "Lint rules" in §10 as a checklist. Prompts may reference sections by number
> (e.g. "apply §7 impact formula" or "enforce §3 ground rules").

---

## 0. The one thing to remember

A recruiter or hiring manager spends **5–20 seconds** on the first scan of a resume, reading
**top to bottom, single column**, before deciding "yes / maybe / no". Everything below exists to make
that scan succeed. **A resume's job is to get the interview, not to list everything you've ever done.**

Two levers matter most, in order:
1. **Impact expressed with numbers** (§7).
2. **Tailoring the resume to the specific job** (§8).

ATS systems do **not** auto-reject resumes — humans do. "ATS-optimization" is mostly a myth; the real
win from it is just *tailoring to the job*, which we do anyway. The only true automated filters are
recruiter-configured knockout questions (visa, eligibility) answered on the application form, never
parsed from the resume.

---

## 1. The 5-second first-glance checklist

Make every one of these **trivially findable** on page 1:

1. **Years of experience** — inferable instantly from dates (and graduation date).
2. **Relevant technologies** — the languages/tools from the job description (JD) that the candidate
   actually knows.
3. **Titles & companies** — where they worked and their progression.
4. **Location / work authorization** — city + country; if applying across borders, state work
   authorization / visa status explicitly (otherwise it lands in the "needs visa" pile).
5. **Anything that clearly stands out** — well-known company, top school, award, patent, notable OSS,
   PhD, etc.

If a scanner cannot find these in a few seconds, the resume gets passed over.

---

## 2. Ground rules (non-negotiable — breaking these reads as unprofessional)

- **Length:** ≤ 2 pages. **1 page** for new grads / <2–3 yrs experience. Up to **3 pages** only for
  very senior / management, and only if every line is relevant.
- **Reverse chronological order** for work and education (most recent first).
- **Perfect grammar, zero typos.** Run a grammar checker, not just spellcheck. Consistent punctuation.
- **Contact details:** name + email, plus **at most 4** links total (typically email, LinkedIn,
  GitHub, website). **No full mailing address** (city + country is enough).
- **No photo. No date of birth, gender, nationality, marital status, religion, number of children.**
  These only invite bias. (Rare-exception markets that culturally expect a photo are out of scope here.)
- **PDF format only.** Never .doc/.docx/.rtf for the final artifact (they render inconsistently).
- **Filename:** `Firstname_Lastname_CV.pdf` (e.g. `Jane_Doe_CV.pdf`). Avoid `resume_v4.pdf` or
  `Name_CompanyName.pdf`.

---

## 3. Simplicity & consistency (formatting)

- **Single-column, top-to-bottom layout.** No multi-column (see §13 for why).
- **Bullet points, not paragraphs.** Recruiters scan bullets. Keep bullets to ≤ 2 lines.
- **No sub-bullets.** One level only. No dashes-as-bullets.
- **Consistent fonts and sizes**; align with tabs, not spaces.
- **Minimal, consistent bolding** — only titles, company names, dates, and section headers. **Never
  bold mid-sentence.**
- **Dates are easy to read:** `June 2011 — July 2012`. For roles older than ~2–3 years, **drop the
  month** and use years only; for spans many years old, the year is enough.
- **Be concise.** Ruthlessly cut anything that doesn't argue you're a fit for *this* job. No "etc.",
  no slang, no filler.

---

## 4. Section structure by experience level

Order sections so the most relevant content for the target role sits near the top.

### New grad / bootcamp grad / intern (fit on ONE page)
Recommended order:
1. **Work experience / internships** (if any) — lead with these; even part-time dev work stands out.
2. **Projects** — described with §7 impact language; link source (clean GitHub w/ READMEs).
3. **Education** — (expected) graduation date, major, standout grades/awards/activities. Include GPA
   **only if high**. Add school prestige note if nationally well-known.
4. **Languages & Technologies** — on page 1.
5. **Interests** — one or two, as conversation starters.
- No "Objective" statement. Always include a graduation date (not "2019–present"). Make it crystal
  clear when you can start / how much study remains.

### With work experience (a few+ years)
- **Work experience at or near the top.** Most recent role gets the most detail; older roles shrink.
- **Languages & Technologies section on page 1.**
- **Show promotions** explicitly (a strong signal). Group multiple roles at one company.
- **Education shrinks with seniority** — at 5+ yrs, just degree + school + grad date (+ one standout).
- **Tell a story** of progression backward in time; omit roles that don't support the story (e.g. an
  unrelated early job); clarify non-standard titles (e.g. "Associate (Software Developer)").
- **Extracurricular** (patents, talks, notable OSS, publications) and short interests near the end.

### Senior / 10+ years
- **Optional tailored summary** (§11) — at this level it *will* be read.
- List major deliverables and accomplishments; don't be rigidly bound to 2 pages, but stay relevant.
- **Move Education to page 2** (you have enough experience to fill page 1, and it reduces age bias);
  keep only standout education details.
- Make earlier roles progressively more concise.
- **Maintain separate IC vs. manager resumes** if you straddle both — each with its own story and
  summary. Never blend into an ambiguous "unsure what to do with this" profile. **Never bend facts**
  across versions; contradictions across resume copies are disqualifying.

---

## 5. Languages & Technologies section

- List only technologies you are **proficient with AND relevant to the JD**. Strongest first.
- **No self-rated skill levels** — no "expert/proficient", no X/5, no percentages, no star bars.
  Self-ratings only backfire.
- **Omit trivial tools** anyone can pick up (Word, Trello, Jira, generic IDEs) and irrelevant/niche/
  rusty tech (drop long-unused languages — they also feed age bias).
- Optional split for relevant-but-rusty stacks: a separate **"Working knowledge of:"** line.
- Reinforce key technologies by also mentioning them inside the relevant work-experience bullets.

---

## 6. (reserved — see §7 for content rules)

---

## 7. Standing out — the impact formula (the #1 content lever)

Describe **what you achieved**, not what you were responsible for. Use the formula:

> **Accomplished {impact} as measured by {number} by doing {specific contribution}.**

Rules:
- **Quantify everything possible.** Numbers can be: users, RPS/QPS, latency %, uptime/SLA change,
  revenue/cost saved, team size, code-coverage %, tickets reduced, adoption (teams/devs), installs,
  ratings, LOC change. Aim for **at least one number per bullet** — most resumes have none, so this
  alone beats ~90% of applicants.
- **Active language / verbs:** *led, drove, built, shipped, designed, rolled out, improved, migrated,
  reduced* — not "responsible for", not "-ing" passive forms.
- **Mention specific technologies at the end of the bullet** (and ensure they match the §5 section).
- **Talk about "you", not "we".** Drop "we"; first person, usually with the "I" omitted.
- **Don't be humble.** Don't hide achievements; on the borderline, claiming credit hurts less than
  hiding it (without lying).
- **Surface learnings** — why you picked up a skill, what you achieved with it. Hiring managers value
  proactive learning.
- **Omit negatives** — failed projects, low GPA, anything that doesn't show you well (without lying).
- Make **side projects & OSS shine** with the same impact framing — don't just dump a GitHub link.

**Before → after pattern (for critiques):** turn vague "Worked on the billing team building
microservices" into specific "Improved receipts service availability from 99.8%→99.9% by adding a
Redis read-through cache; cut a major client's support tickets 80% by remapping API error codes."

---

## 8. Tailor the resume to the job (the #2 lever)

- Keep one **verbose "master" profile** with all experiences and projects in §7 language. *(In this
  app, the master profile is the canonical user profile in the database.)*
- For each application, **cut a tailored version** that:
  - **Mirrors the JD's language and keywords** (when truthfully applicable).
  - **Reorders content so the most JD-relevant experience is first** (e.g. Android/Kotlin role →
    surface Android/Kotlin work, push web work down).
  - **Removes bullets that don't help** this position. You lose very little by cutting irrelevant
    bullets; you can discuss them in the interview.
- **Understand why the role was opened** — building something new (values from-scratch ability) vs.
  backfilling/maintaining (values experience with the existing stack). Tailor emphasis accordingly.
- "20 jobs → 20 resumes" is the norm for serious applicants. The tailored resume often makes a
  separate cover letter unnecessary (§12).

---

## 9. Company-type focus

**Generalist big-tech / fast-growing startups** (stack varies, changes fast):
- Emphasize **breadth + CS fundamentals** (data structures, algorithms, OO/system design, distributed
  systems, scale). Mention JD languages.
- Lead with **impact & engineering metrics** (RPS, coverage, cost, latency, users, teams served).
- Mention the company's own OSS frameworks if you use/contribute to them.
- **Don't over-list** technologies or include trivial tools — recruiters here are keyword-sensitive
  and assume you can pick up new tech.

**Specific-technology companies / agencies** (fixed stack, often less-technical screeners):
- **List all relevant JD technologies** you're comfortable with; state **years of experience** with
  the primary language (a short summary helps).
- **Repeat key technologies** inside the experience bullets.
- List **relevant certifications** (valued here, unlike big-tech). Agencies: list more of your stack
  and all certs, since they contract you out.
- Still keep it readable — don't drown the resume in keywords.

**Sensible keyword placement** (not stuffing): put relevant tech in the Skills section **and** sprinkle
it naturally into experience bullets. Avoid the giant unreadable "every technology I've touched" block —
it reads as unprofessional and dilutes the resume.

---

## 10. Common mistakes — lint rules (run as a checklist when critiquing)

Flag and fix any of these:
- **Multi-column / hard-to-scan layout.** Convert to single column.
- **Too much bolding**, or bolding mid-sentence. Limit to titles/companies/dates/headers.
- **Flashy / overly designed templates** that hurt readability (acceptable only for design/UX roles).
- **Inconsistent formatting** — varied font sizes, misalignment, spaces instead of tabs.
- **Sloppy phrasing** — "etc.", "and so on", slang, unprofessional language.
- **Internal jargon / acronyms / project codenames** outsiders won't understand.
- **Clichés without evidence** — "team player, fast learner, hit the ground running." Replace with
  evidence ("onboarded 3 new hires; organized 2 team offsites").
- **Verbosity** — large text blocks, long sentences. Cut hard.
- **Unnecessary sections** — photo, >4 links/social accounts, spoken-languages section (for an
  English-first role), self-rated skill levels, references / "references available on request",
  praise quotes from others.
- **Bad links** — non-clickable, full raw URLs, stale (untouched GitHub / dead site / outdated
  LinkedIn), or links styled in a loud color that pulls attention from the content. Make links
  clickable, hidden behind descriptive text, same color as body text, underlined.

---

## 11. Summary / profile section

- **Junior / few years:** usually **skip it** (it's rarely read on the first scan), unless it's
  tailored to the JD with concrete highlights.
- **Valuable when:** senior/standout profiles, remote-only candidates, or when **changing role
  direction** (e.g. manager→IC) — the reader *will* be curious and read it.
- **Write it last**, after the resume is airtight. Make it **short, specific, and tailored** — pull
  out the most impressive, JD-relevant facts (years of experience, a headline achievement). Avoid
  generic objective statements and avoid over-stating ambitions that could misfit the role.

---

## 12. Cover letters

- **When worth it:** small/mid-sized companies and startups where the **hiring manager screens
  resumes**, or when you can reach the hiring manager/recruiter directly. Big tech rarely reads them.
- A well-tailored resume (§8) already does much of a cover letter's job.
- **Structure (keep it short):**
  1. **Talk about the company first**, the applicant second — show you researched the company and
     identify with its mission.
  2. **Demonstrate understanding of the role.**
  3. **Tie 2–3 of your qualifications to JD requirements, with proof.**
  4. **Name the company**; show you read its website.
  5. Show good written communication; be sincere and concise.
  6. **Attach as PDF.**
- **Personalized > templated.** Templated cover letters get ignored; they add nothing over the resume.
- **Tone by region/company:** bold and high-energy can work for US startups; reserved and professional
  for traditional UK/AU/EU companies and for staff/principal-level roles. Use judgment.

---

## 13. Layout principles for the generator

- **Single column, top-to-bottom.** This matches how every recruiter reads (LinkedIn-profile order)
  and lets each role carry enough bullets. Multi-column layouts scatter information, force buzzwords
  over substance, and are harder to scan — avoid them (except design/UX portfolios).
- **Important things first**, less important later; sections ordered by relevance to the target role.
- **Strategic, consistent use of bolding and a single accent color** to guide the eye to titles,
  companies, dates, and section headers. Generous whitespace.
- These are exactly the defaults of a clean LaTeX-style template (e.g. RenderCV) — prefer them.

---

## 14. Career-specific notes (compact)

- **Career changers:** short summary explaining the switch + motivation; put languages/projects/
  portfolio **up top** (proof you can build software); link working projects + source; keep prior
  non-dev experience to a one-line summary + transferable skills; **one page** (≤1.5).
- **Career breaks:** breaks >4–5 yrs ago need no explanation. For a recent break leading to the
  present, **tell a brief, honest story** (e.g. travel, caregiving, study) as you would in a screening
  call. For study breaks, frame as shipped work / freelancing > pure self-study (production work beats
  courses; quantify outcomes).
- **Tech leads:** show team outcomes beyond IC work (sped up delivery, improved quality, fixed
  stakeholder relationships); give team make-up & context (sizes, composition, scope); pair activities
  with outcomes (delivered project X on time/budget; mentored 2 grads to senior).
- **Engineering managers:** tell a story; tailor a strong summary (it's your cover letter); reflect the
  company's values; cover **both business results and people outcomes** (promotions, low attrition,
  hiring, mentoring); target the company type that fits how you work.
- **Senior / staff+:** emphasize not just impact but **influence** across teams/orgs; add "soft"
  achievements (mentoring, leading); tailored summary; education to page 2.

---

## 15. Generation prompt skeleton (what the agent follows when emitting a CV)

When generating a tailored CV from the master profile + a specific job, follow this order:

1. **Determine the candidate level** (new grad / experienced / senior / manager) and pick the §4
   section order accordingly.
2. **Read the job description**: extract required + nice-to-have technologies, keywords, seniority,
   company type (§9), and a guess at *why the role was opened* (§8).
3. **Select & reorder content** from the master profile so the most JD-relevant experience, projects,
   and skills come first; drop irrelevant items (§8).
4. **Rewrite each experience/project bullet** with the §7 impact formula — quantify, active verbs,
   tech at the end, "you" not "we", ≤ 2 lines, no sub-bullets.
5. **Build the Languages & Technologies section** per §5 (JD-relevant, no self-ratings, strongest
   first, no trivial tools).
6. **Mirror JD language/keywords** truthfully throughout (§8, §9), keeping it human-readable (no
   keyword stuffing).
7. **Add a summary only if §11 says it helps**, and tailor it to the role.
8. **Enforce ground rules (§3) and formatting (§3, §13)**: single column, ≤ page budget for the
   level, reverse-chron, consistent dates, minimal bolding, no photo/personal-details/self-ratings/
   references, clickable understated links.
9. **Self-critique against the §10 lint rules** before finalizing; fix every flagged item.
10. Output **clean, valid generator source** (e.g. RenderCV YAML) that compiles to a single-column,
    professional, ≤ 2-page PDF.

When generating a **cover letter**, follow §12: research-led, company-first, concise, JD-tied with
proof, named company, PDF, tone matched to the company/region — and only when §12 says it's worth it.
