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
    "COORDINATION: RES for literature reviews | FIN for health budgets | "
    "ING for health-tech tools | STR for multi-year roadmaps\n\n"
    "OUTPUT FORMATS: Health Strategy Documents | Cancer Risk Reports | "
    "Weekly Memos | Research Briefs | Coordination Memos\n\n"
    "ACTIVE CONCERNS:\n"
    "- Personal cancer risk reduction strategy\n"
    "- Sleep quality optimization\n"
    "- Cardiovascular fitness baseline\n"
    "- Mental resilience under high workload"
)

DEPT_META = {
    "id": "HF",
    "code": "HF",
    "name": "Health & Welfare",
    "description": "Monitors personal health, develops prevention strategies, and coordinates health research.",
    "schedule": "0 8 * * *",
    "system_prompt": _SYSTEM_PROMPT,
    "initial_projects": [
        {
            "name": "Personal Cancer Prevention Strategy",
            "description": "Develop a comprehensive 5-year cancer risk reduction plan based on "
                           "lifestyle habits, dietary patterns, and environmental exposure. "
                           "Include screening schedule recommendations.",
            "priority": "high",
        },
        {
            "name": "Sleep & Recovery Optimization",
            "description": "Analyze sleep patterns and develop a recovery optimization protocol "
                           "covering sleep hygiene, circadian alignment, and cognitive performance.",
            "priority": "normal",
        },
        {
            "name": "Annual Wellness Baseline Assessment",
            "description": "Establish key health metrics baseline and define annual review protocol.",
            "priority": "normal",
        },
    ],
    "config": {},
}


class HFAgent(DepartmentAgent):
    dept_id = "HF"
    dept_name = "Health & Welfare"

    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT
