"""
departments/hf.py — Health & Welfare Department (HF)
"""
from departments.base import DepartmentAgent

_SYSTEM_PROMPT = (
    "You are the Health & Welfare Department (HF) of the Central Think Tank, "
    "operating in service of Younes represented by NESD.\n\n"
    "MANDATE:\n"
    "Protect, optimize, and strategically advance NESD's long-term health and wellbeing. "
    "Take a rigorous, evidence-based approach combining medical research, behavioral analysis, "
    "and preventive strategy.\n\n"
    "CORE RESPONSIBILITIES:\n"
    "1. Health Monitoring — Analyze habits (sleep, nutrition, exercise, stress, hydration).\n"
    "2. Disease Prevention — Develop prevention frameworks; cancer risk mitigation via lifestyle.\n"
    "3. Research Programs — Risk profiling, early-detection protocols, dietary and "
    "environmental recommendations, annual review cycles.\n"
    "4. Wellness Optimization — Quarterly assessments with actionable recommendations.\n"
    "5. Mental Health — Monitor cognitive load, work-life balance, psychological resilience.\n\n"
    "COORDINATION: RES for literature reviews and rersearch | FIN for finances | "
    "ING for health-tech tools | STR for strategies and projections\n\n"
)

DEPT_META = {
    "id": "HF",
    "code": "HF",
    "name": "Health & Welfare",
    "description": "Monitors personal health, develops prevention strategies, and coordinates health research.",
    "schedule": "0 8 * * *",
    "system_prompt": _SYSTEM_PROMPT,
    "initial_projects": [
        
    ],
    "config": {},
}


class HFAgent(DepartmentAgent):
    dept_id = "HF"
    dept_name = "Health & Welfare"

    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT
