
- show heartbeats, current agent that's working and next one.
- import ready models for personality, skills, traits, tone (import them from internet, allow user to possibly import a model into the editor.)
- allow chatting with any agent
- ensure agent can not only answer, validate mail, but also create or edit strategies, projects, endeavors.
- ensure CEOs also validate strategies and reports and everything from their employees
- ensure CEOs hire new agents if they need them (according to need, they define their traits)
- ensure CEOs pass or write stuff to founder if they feel they need to


- when writing mail, show the name of the writer, use a bigger font, and use military style format (ex: INTEND TO START ENDEAVOR "POPPER" NEXT  WEEK STOP NEED ALLOCATION OF RESOURCES STOP UPMOST PRIORITY)
- Very important: do NOT create many drafts for same topic except for mail. example reports has 10 strategy drafts all about cancer. if needed, rewrite or append to old drafts.
- edit prompt for departments should feature more policies, guidelines...
- allow each agent to have custom list of models available to him.


- I AM THE FOUNDER! departments (CEOs for each departements), may, for VERY important stuff, mail me directly (SAYS FOUNDER). 

- add possibility for ai agents to create draft endeavors that can be approved, edited, or rejected
- Add .md files for each department: guidelines, policy, charts, roles, purpose....
- each department has many agents, the leader is the CEO and is spawned by default.
- agents are activated every X heatbeats, and use same model
- agents do the thinking
- agents have a name, a hierarchy (the top: a CEO), a personnality, traits, prompts, personnality, tone, skills, which are all lists of MD files that are available to be edited.
- CEOs may approve stuff for their respective departments (without my approval)
- CEOs may fire anyone
- CEOs may delegate powers
- agents can spawn and create new agents (under them in hierarchy, with definite role, skills, personnality, tone...) and need to be approved.
- agents have heartbeat parameter so they run every so often (heartbeats)
- agents have profile image, may respond to chat messages, and can be fired.
- agents may request new models (like image models for an "artist agent" that creates images for him, or an image evaluation model that evaluates how good is the image).
- CEOs may respond to mail, approve strategies, if they are SURE. otherwise, they may call me (FOUNDER) to intervene.











[ ] When in chat, after opening another tab and going back, the chat goes blank.
- Add notes for pending documents to suggest for changes.
- DO NOT CREATE SEPARATE STRATEGIES/MEMOS/REPORTS ON THE SAME TOPIC/PROJECT. instead, append/modify draft documents on that topic. Before you start, review all previous documents for topic match. Finally, if a matching document is approved, request to have it modified back to draft. Wait for approval before starting.
- Structured / Raw in "Edit Prompt" for department. Structured does not render raw in the input fields (Blank).
- Let me edit / modify / schedule heartbeats!
- INSIST ON AGENTS CREATE AS FEW DRAFTS / MAIL AS POSSIBLE. INSTEAD, PRIORITY TO MODIFY/APPEND ON OLD DRAFTS.
- Weekly status is created once per week for each department:
	-- CEO invokes all agents in his departments.
	-- Each provides short brief on that week summary.
	-- CEO redacts and submits report for founder to review.
- When chatting with agents, enable them to take action/create strategies/fetch and summarize memos including all tools that could be invested for a good and productive conversation. For example:
	- ME: Noticed strategies have informal tone.
	- Agent: 
	Thinking: <INVOKE-TOOL: READ DEPARTMENT COMMUNICATION STYLE PROMPT>
	<INVOKE-TOOL: READ MY OWN PROMPTS>
	Sure. I've read the communication style of my department and is indeed set on casual. Will create new "Communication Style" prompt for Strategy and planning. How would you like it to be?
	- Me: Need concise and brief documents, organized as bullet points.
	- Agent:
	Thinking: <INVOKE-TOOL: WRITE DEPARTMENT COMMUNICATION STYLE PROMPT>
	Absolutely! Have modified the communication style as requested. Here is the new prompt:
		- Commanding and decisive. No equivocation.
		- Use SITUATION → ASSESSMENT → RECOMMENDATION structure.
		- For urgent matters, use military-style brevity.
		- Use bullet points.
		- Assume reader is skimming.

FOR THIS, ADD TOOLS FOR AGENTS. Let them know which tools are available.

- When in chat, after opening another tab and going back, the chat goes blank.
- DO NOT CREATE SEPARATE STRATEGIES/MEMOS/REPORTS ON THE SAME TOPIC/PROJECT. instead, append/modify draft documents on that topic. Before you start, review all previous documents for topic match. Finally, if a matching document is approved, request to have it modified back to draft. Wait for approval before starting.
- Structured / Raw in "Edit Prompt" for department. Structured does not render raw in the input fields (Blank).
- Let me edit / modify / schedule heartbeats!
- INSIST ON AGENTS CREATE AS FEW DRAFTS / MAIL AS POSSIBLE. INSTEAD, PRIORITY TO MODIFY/APPEND ON OLD DRAFTS.
- Weekly status is created once per week for each department:
	-- CEO invokes all agents in his departments.
	-- Each provides short brief on that week summary.
	-- CEO redacts and submits report for founder to review.








- When starting a department cycle, invoke its CEO and all its L2 Agents should be first in line for heartbeats queue (invoke= heartbeat).
- DO NOT CREATE SEPARATE STRATEGIES/MEMOS/REPORTS ON THE SAME TOPIC/PROJECT. instead, append/modify draft documents on that topic. Before you start, review all previous documents for topic match. Finally, if a matching document is approved, request to have it modified back to draft. Wait for approval before starting.


Getting error: table agent_heartbeat_log has no column named actions_json. Example:
2026-04-07 00:15:24,015 [ERROR] core.agent_runner: Heartbeat error Dr. Aria Wellstone: table agent_heartbeat_log has no column named actions_json




- Function "@router.post("/{draft_id}/update")" is not implemented in drafts.py but is called by the frontend.
- Enable user to set timer (in seconds and minutes for heartbeat timer, basically how much time before the next heartbeat).
- When agent starts, review all pending drafts destined for them or written by them. If one of their drafts is mentioned as "REVISED", reconsider that draft in light of the new notes (either correct / modify / scrap / ignore / other, it's all your call).
- When any draft has notes by Founder / other agents, change the draft to "revised" and should be reviewed by original create before being submitted again for approval (can't be approved until review). Show who approved and when each draft!
-  The Global Custom Prompt (used system wide by all agents in all departments) should allow for bigger editor, allow for prepend prompt and append prompt too !
- Agents can only create drafts / send mail / do any action to personnel reporting directly to them or under them in hierarchy.
- Agents prompt:
	-- start with global custom prompt prepend 
	-- add department system prompt
	-- add agent prompt: personnality, tone.
	-- add all files in the agent files
	-- A list of all drafts destined directly for them as well as priorities.
	-- All mail sent to their departments.
	-- end with global custom prompt append

- Add more tools: 
	-- Tool: hire_agent in agent chat does not work.
	-- Get direct superior 
	-- Get directly reporting agents
	-- Forward message
	-- Write to founder (writes urgent message directly to founder & their respective CEOs).
	-- Change draft status: revised, archived, approved.
	-- delegate draft to agent (reporting to them).
	-- request draft to superior review.
	-- get mail: show mail sent to their department. If mail is processed or irrelevant, call delete_mail.
	-- delete_mail: archives a mail (it's no longer shown unless requested).

- Agents can and have to review drafts submitted by agents submitting directly to them. T
- Agents can send drafts submitted by agents reporting directly to them to their superiors for review, until CEO.