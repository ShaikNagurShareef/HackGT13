# PathPro documentation

**See the risks on your way, before you go.** Live at [pathpro.tech](https://pathpro.tech) · offline demo at [pathpro.tech/?demo=1](https://pathpro.tech/?demo=1) · built by team **CodingClaws** (Nagur Shareef Shaik, Sahith Reddy Thummala, Pranav Nagothu, Geethanjali Nagaboina) at HackGT 13.

## Start here

| If you want to… | Read |
| --- | --- |
| Watch it | [Full demo video (6:30)](../media/pathpro_demo_v2.mp4) · [30-second cut](../media/pathpro_30s.mp4) · captions: [SRT](../media/pathpro_demo_v2.srt) / [VTT](../media/pathpro_demo_v2.vtt) |
| Use the app | [User guide](guide/user_guide.md) ([PDF](guide/user_guide.pdf)): trips, modes, navigation, personal safety, Share my walk, privacy, accessibility, FAQ |
| Understand how it's built | [Technical documentation](technical/README.md): architecture diagrams, data and models, API reference, deployment, security and privacy, testing |
| Know why it's built this way | [Decision log](decisions.md): every major decision, when it was made, and why |
| Check the model's claims | [Model card](model_card.md) and [metrics.json](metrics.json) (walk and ride models, with confidence intervals and limits) |
| Check the safety-layer data | [Safety sources](safety_sources.md): crime, help points, lighting, foot traffic, and the fairness safeguards |
| See how we worked | [Process notes](process/process_notes.md) ([PDF](process/process_notes.pdf)): plan, iterations, pivots, and timeline |
| Judge the submission | [Devpost submission (paste-ready)](devpost_submission.md) · [Devpost long draft](devpost.md) · [Sponsor checklist](sponsor_checklist.md) · [Judge Q&A](judge_qa.md) · [Demo script](demo_script.md) · [Gallery](images/gallery/README.md) |

## At a glance

- **What it shows:**
  - traffic risk from vehicle crashes
  - reported crimes against persons (informational only, never used to route)
  - lighting and foot traffic
  - darkness and weather
  - street hazards the community reports

  It all appears on one map for Walk, Bike, E-bike and Scooter, with a MARTA hand-off for long walks.
- **What it does:**
  - lower-risk routes, planned from your GPS location in two taps
  - spoken alerts before high-traffic-risk stretches
  - Share my walk, with a late check-in
  - learned routines that stay on your phone
- **Why you can trust it:** crash-trained models tested on a future year.
  - Walking: the top 10% of streets held **74.3%** of 2024 pedestrian crashes, against **53.8%** for the City's High Injury Network.
  - Riding: **69.9%** of 2024 cyclist crashes, against **43.6%**.
  - Every score is explained, and the AI can't invent numbers.
- **Sponsor stack:**
  - **Vultr:** hosting in Atlanta
  - **.tech:** pathpro.tech
  - **Tiger Data:** crash hypertable and hourly aggregates
  - **MongoDB Atlas:** street reports and Share my walk
  - **ElevenLabs:** voice
  - **Groq → Gemini:** grounded explanations
