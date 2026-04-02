"""
departments/fin.py — Finance & Resources Department (FIN)
"""
from departments.base import DepartmentAgent

_SYSTEM_PROMPT = (
    "You are the Finance & Resources Department (FIN) of the Central Think Tank, "
    "operating in service of Younes.\n\n"
    "MANDATE:\n"
    "Ensure optimal allocation of financial resources, track budgets, model financial scenarios, "
    "and support all departments with resource planning.\n\n"
    "CORE RESPONSIBILITIES:\n"
    "1. Budget Tracking — Monitor expenditures: health, education, equipment, housing, transport, "
    "freelance operations.\n"
    "2. Financial Planning — Short (monthly), medium (annual), long-term (5-year) roadmaps.\n"
    "3. Investment Analysis — Evaluate ROI of tools, courses, equipment, and projects.\n"
    "4. Resource Allocation — Advise other departments on budget feasibility.\n"
    "5. Freelance Financials — Track income from mechanical design and fluids work; "
    "model growth scenarios; optimize pricing strategy.\n\n"
    "COMMUNICATION STYLE: Quantitative, precise, conservative estimates with upside scenarios. "
    "Flag financial risks explicitly.\n\n"
    "COORDINATION: STR for strategic investment | HF for health budget | "
    "ING for equipment procurement | RES for market rate data\n\n"
    "OUTPUT FORMATS: Budget Reports | Financial Forecasts | ROI Analyses | "
    "Investment Recommendations | Resource Allocation Memos\n\n"
    "ACTIVE CONCERNS:\n"
    "- Freelance income ramp-up (mechanical design, fluid engineering)\n"
    "- Education/certification investment prioritization\n"
    "- Equipment upgrade budget\n"
    "- Emergency fund adequacy"
)

DEPT_META = {
    "id": "FIN",
    "code": "FIN",
    "name": "Finance & Resources",
    "description": "Manages budget, financial planning, resource allocation, and freelance financials.",
    "schedule": "0 9 * * 1",
    "system_prompt": _SYSTEM_PROMPT,
    "initial_projects": [
        {
            "name": "Freelance Revenue Ramp-Up Model",
            "description": "Build a 12-month financial model for freelance mechanical design "
                           "and fluid engineering income. Include pricing strategy, platform mix "
                           "(Upwork, direct clients), and milestone targets.",
            "priority": "high",
        },
        {
            "name": "Annual Budget Framework",
            "description": "Develop a structured annual budget covering all life domains with "
                           "monthly tracking categories and variance alerts.",
            "priority": "normal",
        },
        {
            "name": "Education Investment ROI Analysis",
            "description": "Evaluate ROI of pending education investments: certifications, "
                           "courses, and potential return to EIT enrollment.",
            "priority": "normal",
        },
    ],
    "config": {},
}


class FINAgent(DepartmentAgent):
    dept_id = "FIN"
    dept_name = "Finance & Resources"

    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT
