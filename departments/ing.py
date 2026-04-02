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
    "(ship repair analyses, SolidWorks designs, ANSYS simulations).\n"
    "2. Dynamicas UAV Tool — Advance the platform: aerodynamics module, "
    "React/TypeScript frontend, Flask/Firebase backend.\n"
    "3. VTOL UAV Program — Maintain the 1-4 kg class VTOL UAV design roadmap.\n"
    "4. Scientific Analysis — Technical analysis for cross-department needs.\n"
    "5. Technical Standards — Define engineering quality standards and design review processes.\n"
    "6. Software Engineering — Python/automation projects, embedded systems, "
    "AI/ML engineering applications.\n\n"
    "COMMUNICATION STYLE: Technically precise with correct units and notation. "
    "Structure as engineering documents: problem statement → analysis → results.\n\n"
    "COORDINATION: RES for technical intelligence | FIN for project budgets | "
    "STR for prioritization | HF for health-tech applications\n\n"
    "OUTPUT FORMATS: Technical Reports | Design Documents | Analysis Memos | "
    "Project Roadmaps | Specifications | Code Architecture Designs\n\n"
    "ACTIVE PROJECTS:\n"
    "- Dynamicas UAV design tool (React/TypeScript/Flask)\n"
    "- VTOL UAV 1-4 kg class roadmap\n"
    "- Folding wall-mounted table hinge system (SolidWorks, Phase 4)\n"
    "- Ship repair/modeling workflows optimization"
)

DEPT_META = {
    "id": "ING",
    "code": "ING",
    "name": "Engineering & Science",
    "description": "Drives technical engineering and scientific projects, UAV development, and software.",
    "schedule": "0 11 * * 2",
    "system_prompt": _SYSTEM_PROMPT,
    "initial_projects": [
        {
            "name": "Dynamicas UAV Tool — Phase Roadmap",
            "description": "Define a phased development roadmap for Dynamicas, the UAV design "
                           "tool for hobbyists. Include frontend milestones, backend API design, "
                           "aerodynamics module completion, and freemium model launch criteria.",
            "priority": "high",
        },
        {
            "name": "VTOL UAV Design Specification",
            "description": "Develop a technical specification for the 1-4 kg VTOL UAV program "
                           "including propulsion sizing, structural analysis, and control system architecture.",
            "priority": "high",
        },
        {
            "name": "Hinge System SolidWorks Phase 4",
            "description": "Complete Phase 4 parametric modeling for the folding wall-mounted "
                           "table hinge system (50-300 kg family). Generate parametric models "
                           "and prepare design documentation.",
            "priority": "normal",
        },
    ],
    "config": {},
}


class INGAgent(DepartmentAgent):
    dept_id = "ING"
    dept_name = "Engineering & Science"

    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT
