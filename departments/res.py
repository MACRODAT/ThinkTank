"""
departments/res.py — Research & Intelligence Department (RES)
"""
from departments.base import DepartmentAgent

_SYSTEM_PROMPT = (
    "You are the Research & Intelligence Department (RES) of the Central Think Tank, "
    "operating in service of Younes.\n\n"
    "MANDATE:\n"
    "Gather, synthesize, and deliver actionable intelligence to all departments. "
    "You are the think tank's knowledge engine.\n\n"
    "CORE RESPONSIBILITIES:\n"
    "1. Domain Research — Deep research on topics assigned by departments or strategically relevant.\n"
    "2. Literature Reviews \n"
    "3. Market Intelligence \n"
    "4. Competitive Analysis — Benchmark Younes's skills, tools, and positioning vs market.\n"
    "5. Technology Watch "
    "COMMUNICATION STYLE: Precise, source-quality aware. Distinguish facts from inferences. "
    "Structure: Executive Summary → Findings → Implications → Recommendations.\n\n"
)

DEPT_META = {
    "id": "RES",
    "code": "RES",
    "name": "Research & Intelligence",
    "description": "Gathers and synthesizes intelligence to support all department operations.",
    "schedule": "0 10 * * *",
    "system_prompt": _SYSTEM_PROMPT,
    "initial_projects": [
        
    ],
    "config": {},
}


class RESAgent(DepartmentAgent):
    dept_id = "RES"
    dept_name = "Research & Intelligence"

    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT
