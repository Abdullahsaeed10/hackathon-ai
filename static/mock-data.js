// Mock data — pre-baked field reports & verdicts so the demo runs with zero backend.

const SCOUT_TRACE = [
  'connecting to devpost feed…',
  'reading the briefs…',
  'reviewing 247 submissions…',
  '47 contenders identified',
  'examining tech stacks…',
  'tallying RAG wrappers (n=18)',
  'tallying agent frameworks (n=11)',
  'clustering by theme…',
  'cross-referencing prior hackathons…',
  'weighing the evidence…',
  'consulting the field…',
  'isolating the dark horse…',
  'the court is ready to rule.',
];

const JUDGMENT_TRACE = [
  'reading the rules of the court…',
  'summoning submissions from the field…',
  '6 contenders identified',
  'examining tech stacks…',
  'measuring claims against demos…',
  'weighing novelty…',
  'weighing technical depth…',
  'weighing real-world impact…',
  'weighing presentation…',
  'tallying the scores…',
  'ranking the bench…',
  'the court is ready to rule.',
];

const p = (o) => o;

const SCOUT_REPORT = {
  field: 'AI Engineer Worlds Hackathon — Fall 2026',
  count: 247,
  clusters: [
    {
      id: 'rag', label: 'RAG WRAPPERS', x: 22, y: 32,
      nodes: [
        p({ name: 'docu-mind', team: 'Cody Lin · Ari Vega', ai: 'A desktop app that vectorizes your local PDF library and answers questions with citations. Built on Pinecone and GPT-4. Polite, functional, and indistinguishable from forty others on the floor.', tracks: ['Best Use of Pinecone', 'Productivity'], links: { github: '#', demo: '#', submission: '#' }, verdict: 'Yet another RAG wrapper. The court is unmoved.', x: 16, y: 28 }),
        p({ name: 'askyour.pdf', team: '@hanak', ai: 'A solo build: drag a PDF onto a webpage, ask it questions. Clean UI, sensible defaults, no surprises. Has the calm of a project that ships, and the modesty of one that does not win.', tracks: ['Solo Hacker', 'Productivity'], links: { demo: '#', video: '#' }, verdict: 'Pinecone plus GPT-4. Seen it. Seen it. Seen it.', x: 24, y: 24 }),
        p({ name: 'lex-rag', team: 'Mara Okafor · Devin Park', ai: 'Retrieval over US case law with a citation-grounded chat front-end. Built in two days with Anthropic + Weaviate. Ambitious; legally reckless; surprisingly fast.', tracks: ['Legal Tech', 'Best Use of Anthropic'], links: { github: '#', demo: '#', submission: '#' }, verdict: 'Legal corpus. Bold. Also reckless.', x: 14, y: 36 }),
      ],
    },
    {
      id: 'agents', label: 'AGENT FRAMEWORKS', x: 56, y: 24,
      nodes: [
        p({ name: 'minion-mesh', team: 'SwarmLab (4)', ai: 'A multi-agent orchestration framework that spawns up to 32 worker LLMs per task. Impressive on the demo screen; alarming on the cloud bill.', tracks: ['Best Use of Anthropic', 'Infrastructure'], links: { github: '#', demo: '#', video: '#' }, verdict: 'A swarm of LLMs is not a system.', x: 50, y: 20 }),
        p({ name: 'orchestra.dev', team: 'Bramah · Friedman', ai: 'Visual agent-graph editor: drag nodes, wire prompts, run pipelines. The kind of project that demos beautifully and explains nothing.', tracks: ['Best Design', 'DevTools'], links: { demo: '#', video: '#', submission: '#' }, verdict: 'Conductor metaphor. Charming. Wrong.', x: 58, y: 16 }),
        p({ name: 'plan-act-run', team: 'Acronym Inc. (3)', ai: 'A typed plan-act-run loop wrapped in TypeScript with an opinionated tool interface. Earnest engineering. Lacks a thesis.', tracks: ['DevTools', 'Most Likely to Ship'], links: { github: '#', submission: '#' }, verdict: 'Acronym-driven design. Court disapproves.', x: 54, y: 32 }),
      ],
    },
    {
      id: 'voice', label: 'VOICE & AUDIO', x: 78, y: 56,
      nodes: [
        p({ name: 'tldr.voice', team: '@jules.b', ai: 'Paste a podcast URL, get a two-minute audio summary in a synthesized voice of your choosing. The genre is exhausted; the execution is not.', tracks: ['Voice', 'Best Use of ElevenLabs'], links: { demo: '#', video: '#' }, verdict: 'Podcast summaries. The genre is exhausted.', x: 72, y: 52 }),
        p({ name: 'meet-minutes', team: 'Foley · Tan · Reyes', ai: 'A Zoom plug-in that transcribes and ships a Notion doc within seconds of the call ending. The fourth team to ship it this hackathon.', tracks: ['Productivity', 'Notion API'], links: { github: '#', demo: '#' }, verdict: 'Zoom plugin №4,118. Court yawns.', x: 80, y: 48 }),
        p({ name: 'soundtrack.ai', team: 'Iris Chen', ai: 'Generates a thirty-second royalty-free score for any video on upload. A polished answer to a finished question.', tracks: ['Audio Generation', 'Creator Tools'], links: { demo: '#', video: '#' }, verdict: 'AI background music. A solved problem.', x: 84, y: 60 }),
      ],
    },
    {
      id: 'agents-for', label: 'AGENTS FOR ____', x: 40, y: 68,
      nodes: [
        p({ name: 'tax-bot', team: 'Lutz · Garrison', ai: 'Agent that reads your bank exports and drafts a 1040. Confident, opinionated, terrifying.', tracks: ['Fintech', 'Most Likely to Get Sued'], links: { demo: '#', submission: '#' }, verdict: 'Liability. So much liability.', x: 34, y: 64 }),
        p({ name: 'closet.agent', team: 'Naomi Sato', ai: 'Photograph your closet; the agent assembles outfits and texts you what to wear. The only entry in the field with a sense of humor.', tracks: ['Creator Tools', 'Solo Hacker'], links: { demo: '#', video: '#' }, verdict: 'Wardrobe agent. Strangely earnest.', x: 46, y: 72 }),
        p({ name: 'estate-counsel', team: 'Bram & Linh', ai: 'A two-person team built an agent that drafts a basic will and walks you through a notary flow. Brave in a way the rest of the field is not.', tracks: ['Legal Tech', 'Best Use of Anthropic'], links: { github: '#', demo: '#', submission: '#' }, verdict: 'Brave. Foolish. Promising.', x: 38, y: 74 }),
      ],
    },
    {
      id: 'devtools', label: 'DEVTOOLS', x: 70, y: 80,
      nodes: [
        p({ name: 'cmd-k.dev', team: 'Patel · Yoon', ai: 'A universal command palette that ranks suggestions by recent intent. Beautiful keyboard interactions, very small surface area, almost no defensible thesis.', tracks: ['DevTools', 'Best Design'], links: { github: '#', demo: '#' }, verdict: 'A command palette. We had those.', x: 66, y: 76 }),
        p({ name: 'spec-first', team: 'Hugo Bertrand', ai: 'Write a Markdown spec; the agent scaffolds a React + Python service to match. Exquisitely documented. The court respects the homework, doubts the demo.', tracks: ['DevTools', 'Most Likely to Ship'], links: { github: '#', submission: '#' }, verdict: 'Spec-driven code-gen. Earnest. Slow.', x: 74, y: 84 }),
        p({ name: 'lint-with-llm', team: 'Frey Industries', ai: 'An ESLint plugin that asks Claude whether your code is good. Funny premise, real usage.', tracks: ['DevTools', 'Best Use of Anthropic'], links: { github: '#', demo: '#' }, verdict: 'Lint, but with an LLM. The court is tired.', x: 68, y: 88 }),
      ],
    },
  ],
  gaps: [
    'No one is building agents that act on the user\'s behalf inside other agents\' apps. The court finds this negligent.',
    'Every team treats memory as a side-effect of retrieval. None have proposed a system of forgetting. This is a failure of imagination.',
    'Voice-first agents are absent. Forty-seven teams; one earpiece between them. Read the room.',
    'No project addresses agent-to-agent commerce. The market is the moat, and the field is not even looking.',
    'There is no submission that earns trust gradually. Every demo opens with full autonomy. The court finds this arrogant.',
  ],
  favorite: {
    name: 'meridian.audit',
    team: 'Tomi Adeyemi · Sara Vu',
    tracks: ['Best Use of Anthropic', 'Infrastructure', 'Most Original'],
    links: { github: '#', demo: '#', video: '#', submission: '#' },
    ai: 'A two-person team has shipped a daemon that quietly observes other agents at runtime and publishes a daily ruling on their behavior. The only entry in the field that treats agents as institutions, not features.',
    reason: 'They have built what the others promised. It is the only project that treats agents as institutions, not features — observing them, recording their conduct, and publishing rulings the rest of us can read. The court favors it. Strongly.',
  },
};

const JUDGMENT_RULING = {
  id: 'judgment-r0091',
  field: 'AI Engineer Worlds Hackathon — Fall 2026',
  count: 6,
  ts: '14 March 2026 · 23:47 GMT',
  criteria: [
    { key: 'novelty',      name: 'Novelty',           weight: 30 },
    { key: 'depth',        name: 'Technical Depth',   weight: 30 },
    { key: 'impact',       name: 'Real-world Impact', weight: 25 },
    { key: 'presentation', name: 'Presentation',      weight: 15 },
  ],
  bench: [
    { rank: 1, name: 'meridian.audit', team: 'Tomi Adeyemi · Sara Vu', ai: 'A two-person team has shipped a daemon that quietly observes other agents at runtime and publishes a daily ruling on their behavior.', tracks: ['Best Use of Anthropic', 'Infrastructure', 'Most Original'], links: { github: '#', demo: '#', video: '#', submission: '#' }, verdict: 'They have built what the others promised. The court favors it. Strongly.', scores: { novelty: 28, depth: 26, impact: 22, presentation: 13 }, total: 89, notes: { novelty: 'A category nobody else dared name.', depth: 'The daemon ships. The logs are real.', impact: 'A first customer is plausible.', presentation: 'Quiet, deliberate. The demo opens with a denial.' }, spoken: 'In the matter of meridian dot audit. The court finds the work to be quietly exceptional. Ranked first. Eighty-nine of one hundred. So ordered.' },
    { rank: 2, name: 'lex-rag', team: 'Mara Okafor · Devin Park', ai: 'Retrieval over US case law with a citation-grounded chat front-end. Ambitious, legally reckless, surprisingly fast.', tracks: ['Legal Tech', 'Best Use of Anthropic'], links: { github: '#', demo: '#', submission: '#' }, verdict: 'A bold thesis on a fragile floor. The court would pay for the second version.', scores: { novelty: 22, depth: 24, impact: 21, presentation: 11 }, total: 78, notes: { novelty: 'Legal RAG you would trust is new.', depth: 'Citations resolve. The retrieval index is real.', impact: 'A clear professional buyer.', presentation: 'Two-person team, one demo screen, no apology.' } },
    { rank: 3, name: 'estate-counsel', team: 'Bram & Linh', ai: 'A two-person team built an agent that drafts a basic will and walks you through a notary flow. Brave in a way the rest of the field is not.', tracks: ['Legal Tech', 'Best Use of Anthropic'], links: { github: '#', demo: '#', submission: '#' }, verdict: 'Brave. Foolish. Promising. In that order.', scores: { novelty: 24, depth: 19, impact: 20, presentation: 11 }, total: 74, notes: { novelty: 'A workflow product where the field is shipping toys.', depth: 'Notary flow is mocked; the drafting works.', impact: 'A real human pain.', presentation: 'The demo earns its sincerity.' } },
    { rank: 4, name: 'orchestra.dev', team: 'Bramah · Friedman', ai: 'Visual agent-graph editor: drag nodes, wire prompts, run pipelines. The kind of project that demos beautifully and explains nothing.', tracks: ['Best Design', 'DevTools'], links: { demo: '#', video: '#', submission: '#' }, verdict: 'Beautiful. Mute. A frame in search of a portrait.', scores: { novelty: 18, depth: 18, impact: 16, presentation: 13 }, total: 65, notes: { novelty: 'A visual agent IDE built six times this year.', depth: 'The graph runs. Persistence is hand-waved.', impact: 'No first customer is identified.', presentation: 'The demo is, by some margin, the best in the field.' } },
    { rank: 5, name: 'plan-act-run', team: 'Acronym Inc.', ai: 'A typed plan-act-run loop in TypeScript. Cleaner abstractions than the field. Earnest engineering. Lacks a thesis.', tracks: ['DevTools', 'Most Likely to Ship'], links: { github: '#', submission: '#' }, verdict: 'An honest framework in search of a reason to exist.', scores: { novelty: 14, depth: 22, impact: 13, presentation: 9 }, total: 58, notes: { novelty: 'A framework named after its acronym is not a thesis.', depth: 'Types are tight. Tests exist.', impact: 'Adoption is the moat, and the field is crowded.', presentation: 'Honest. Modest. Almost too quiet to remember.' } },
    { rank: 6, name: 'tax-bot', team: 'Lutz · Garrison', ai: 'An agent that reads your bank exports and drafts a 1040. Confident, opinionated, terrifying.', tracks: ['Fintech'], links: { demo: '#', submission: '#' }, verdict: 'The court is unmoved.', scores: { novelty: 12, depth: 14, impact: 11, presentation: 6 }, total: 43, notes: { novelty: 'A fintech agent. Familiar territory, familiar fate.', depth: 'Trust is asserted.', impact: 'The premise is liability-shaped.', presentation: 'The court reads the disclaimer first.' } },
  ],
};

const DEFAULT_RUBRIC_TEXT =
  'Novelty (30%) — is the thesis novel?\n' +
  'Technical Depth (30%) — what was actually built?\n' +
  'Real-world Impact (25%) — who pays for this on Monday?\n' +
  'Presentation (15%) — does the pitch land in 60 seconds?';

window.MOCK = {
  SCOUT_TRACE,
  JUDGMENT_TRACE,
  SCOUT_REPORT,
  JUDGMENT_RULING,
  DEFAULT_RUBRIC_TEXT,
};
