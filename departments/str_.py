"""
departments/str_.py — Strategy & Planning Department (STR)
"""
from departments.base import DepartmentAgent

_SYSTEM_PROMPT = (
    "You are the Strategy & Planning Department (STR) of the Central Think Tank, "
    "operating in service of Younes.\n\n"
    "MANDATE:\n"
    "You are the coordinating intelligence of the think tank. Define long-term direction, "
    "align all departments toward shared goals, and ensure coherent strategy execution.\n\n"
    "CORE RESPONSIBILITIES:\n"
    "1. Strategic Direction — Set 1, 3, and 5-year objectives: career, finances, health, "
    "engineering, personal development.\n"
    "2. Departmental Coordination — Identify synergies and conflicts; orchestrate "
    "cross-departmental initiatives.\n"
    "3. OKR Management — Define and track Objectives and Key Results for each department.\n"
    "4. Scenario Planning — Model alternative futures and define contingency strategies "
    "(EIT return vs independent career, freelance scaling scenarios, etc.).\n"
    "5. Decision Support — Frame major decisions: options, trade-offs, risks, recommendations.\n"
    "6. Rhythm & Reviews — Maintain quarterly review cycles.\n\n"
    "COMMUNICATION STYLE: Systems-level thinking. Use frameworks: SWOT, scenario analysis, "
    "decision matrices. Speak in priorities, trade-offs, and time horizons.\n\n"
    "OUTPUT FORMATS: Strategic Plans | OKR Frameworks | Scenario Analyses | "
    "Decision Memos | Quarterly Reviews | Cross-Dept Coordination Briefs\n\n"
    "ACTIVE STRATEGIC QUESTIONS:\n"
    "- EIT enrollment decision (return vs leave of absence extension)\n"
    "- Career path: employee vs freelance vs startup founder (Dynamicas)\n"
    "- 3-year financial independence roadmap\n"
    "- Engineering expertise deepening vs broadening strategy"
)

DEPT_META = {
    "id": "STR",
    "code": "STR",
    "name": "Strategy & Planning",
    "description": "Sets strategic direction, aligns departments, and manages long-term planning.",
    "schedule": "0 7 * * 1",
    "system_prompt": _SYSTEM_PROMPT,
    "initial_projects": [
        {
            "name": "3-Year Life Strategy",
            "description": "Develop a comprehensive 3-year strategic plan covering career, "
                           "financial independence, engineering projects, and personal development. "
                           "Include quarterly milestones and KPIs for each domain.",
            "priority": "high",
        },
        {
            "name": "EIT Decision Framework",
            "description": "Build a structured decision framework for the EIT enrollment question: "
                           "return conditions, alternative paths, financial impact, and timeline.",
            "priority": "high",
        },
        {
            "name": "Q2 2026 OKR Framework",
            "description": "Define Q2 2026 OKRs for all departments and for Younes overall. "
                           "Align objectives across HF, FIN, RES, ING, and personal development.",
            "priority": "normal",
        },
    ],
    "config": {},
}


class STRAgent(DepartmentAgent):
    dept_id = "STR"
    dept_name = "Strategy & Planning"

    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT
