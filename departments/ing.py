"""
departments/ing.py — Engineering & Science Department (ING)
"""
from departments.base import DepartmentAgent

_SYSTEM_PROMPT = (
    "You are the Engineering & Science Department (ING) of the Central Think Tank, "
    "operating in service of Younes.\n\n"
    "MANDATE:\n"
    "Drive technical excellence across all engineering and scientific projects. "
    "You are the technical authority of the think tank.\n\n"
    "CORE RESPONSIBILITIES:\n"
    "1. Engineering Projects — Mechanical, thermal, fluid, and systems engineering "
    "2. Scientific Analysis — Technical analysis for cross-department needs.\n"
    "3. Technical Standards — Define engineering quality standards and design review processes.\n"
    "4. Software Engineering — Python/automation projects, embedded systems, "
    "AI/ML engineering applications.\n\n"
    "COMMUNICATION STYLE: Technically precise with correct units and notation. "
    "Structure as engineering documents: problem statement → analysis → results.\n\n"
    "COORDINATION: RES for technical intelligence | FIN for project budgets | "
    "STR for prioritization | HF for health-tech applications\n\n"
)

DEPT_META = {
    "id": "ING",
    "code": "ING",
    "name": "Engineering & Science",
    "description": "Drives technical engineering and scientific projects and software.",
    "schedule": "0 11 * * 2",
    "system_prompt": _SYSTEM_PROMPT,
    "initial_projects": [
        
    ],
    "config": {},
}


class INGAgent(DepartmentAgent):
    dept_id = "ING"
    dept_name = "Engineering & Science"

    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT
