
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



1- Fix ERROR:    Exception in ASGI application
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\uvicorn\protocols\http\httptools_impl.py", line 401, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\uvicorn\middleware\proxy_headers.py", line 70, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\fastapi\applications.py", line 1054, in __call__
    await super().__call__(scope, receive, send)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\applications.py", line 113, in __call__
    await self.middleware_stack(scope, receive, send)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\middleware\errors.py", line 187, in __call__
    raise exc
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\middleware\errors.py", line 165, in __call__
    await self.app(scope, receive, _send)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\middleware\cors.py", line 93, in __call__
    await self.simple_response(scope, receive, send, request_headers=headers)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\middleware\cors.py", line 144, in simple_response
    await self.app(scope, receive, send)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\middleware\exceptions.py", line 62, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\_exception_handler.py", line 62, in wrapped_app
    raise exc
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\_exception_handler.py", line 51, in wrapped_app
    await app(scope, receive, sender)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\routing.py", line 715, in __call__
    await self.middleware_stack(scope, receive, send)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\routing.py", line 735, in app
    await route.handle(scope, receive, send)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\routing.py", line 288, in handle
    await self.app(scope, receive, send)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\routing.py", line 76, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\_exception_handler.py", line 62, in wrapped_app
    raise exc
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\_exception_handler.py", line 51, in wrapped_app
    await app(scope, receive, sender)
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\starlette\routing.py", line 73, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\fastapi\routing.py", line 301, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\OMEN\anaconda3\Lib\site-packages\fastapi\routing.py", line 212, in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\ai\central-think-tank\api\routes\drafts.py", line 87, in review
    ok = await review_draft(draft_id, action, notes, reviewed_by)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\ai\central-think-tank\core\draft_vault.py", line 149, in review_draft
    new_content = (row["content"] if row else "") + note_block

2- Fix heartbeat monitor in dashboard which does not show anything.
3- Add tab in department showing hierarchy of all agents
4- Make sure agents create endeavors too (they do not)
5- In order to prevent data duplicates and for more organization:
	- Create topics, so each topic is associated with a theme such as: "Freelancing strategy"
	- The mail room allows filtering mail depending on topic, sender or recepient
	- The projects can be grouped based on topic
	- The drafts can be grouped based on topic
	- Make sure all agents research topic before create a new topic
	- Make sure all agents include topic in all mail, drafts, strategies...
	- Feel free to add feature / apply ideas as you see fit



Continue. Also include:


- const PRESET_LIBRARY in ModelImporter.jsx should feature external *.json folder.
- The agent's personnality, tone, skills should be infered from the files in his profile. When the agent needs to process ANY content, first start by importing ALL the files in his profile. Whenever a file is added (personnality, skill, Tone), redefine the agent's profile folder (his personnality, tone) from the files used. These inputs SHOULD be read only.
- Only ONE personnality is allowed for each agent.
- Allow importing images and files for any agent. Also allow changing agent profile image !
- Whenever any agent is spawned, get his profile image from "https://thispersondoesnotexist.com/". Also, add button to retry for another image (same source).  
- Allow viewing / editing ALL prompts of Centrale, including system prompts, agent prompts, etc. Explain thoroughly what each does.
- Agents keep creating new endeavours when they already exist (Ensure they modify existing endeavors, even if they are approved, an endeavor can be modified with new phases and tasks constantly).  


- show all edits to drafts / strategies / mail
- When I reply to anything in my founder inbox, such as CEO mails, spawn requests, and draft endeavor, prioritize a reply from the concerned agent (ideally immediate, if many, put a queue)/
- random profile image does not work (Could not fetch face: not found)
- Example of erroneous conversation:
  -- ME: Hire a mechanical engineer
  -- Agent: calls create_draft (instead of hire_agent)
  ⚠ Existing draft found: 'Weekly Status — Engineering & Science — 2026-04-08' (id: xx, status: approved). Use update_draft instead.
Use correct tools !
- When any draft / note / strategy has any modifications or status modifications (such as approved), ensure you log who and when he approved it (better add remarks for approval!)
- Agents should prioritize update_draft
- Projects just keep getting created (in few hours I get dozens of projects on similar topics). Same for endeavors
- Add more settings (fonts, theme, etc.)

Continue and add:
- ALL prompts (such as lines 269 in agent_runner.py) should be available for edit. No hard coded prompts !!
- add web_search tool for agents, its configuration in settings with a strong reliable framework
