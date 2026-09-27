# PathPro demo script

**Presenter:** Nagur Shareef Shaik (solo build, team name Coding Claws).
**Setup:** laptop on the app with `?demo=1` (scripted demo, works offline). Phone on the live app at https://pathpro.tech (Vultr). Printed QR code and model card on the table.
**Demo shortcuts:** `D` reload the scripted route · `T` jump to 10 PM · `R` toggle rain.
**New features:** "Imagine this street redesigned" and Ask PathPro are hidden in `?demo=1` and are not yet deployed to pathpro.tech. Use the beats marked *(after deploy)* only once they work on the live site.

## 30-second version (for judges walking by)

> "Map apps optimize one number: time. PathPro adds the one they ignore — where people on foot actually get hit by cars.
> I trained a model on five years of Atlanta crash records. Here's Klaus to Midtown MARTA at 10:30 on a rainy Friday: the fastest route runs down Peachtree Place and Williams Street. PathPro finds one that's **4 minutes longer with 54% less traffic-risk exposure**.
> Tap any street and you see exactly why it scores high. And it's honest: on crashes it had never seen, the 10% of Atlanta's streets it flags held **74% of next year's pedestrian crashes** — versus 54% for the City's own High Injury Network."

## 3-minute version

**0:00 — Hook (the problem).**
"We're standing in Klaus. Say you walk to Midtown MARTA tonight at 10:30 in the rain. Google shows you an 18-minute walk. It doesn't show you that the walk runs along some of Atlanta's highest-risk streets for pedestrians."

**0:20 — Wow moment (the route).** Press `D`.
"This is PathPro. Grey is the fastest route, teal is PathPro's. **Plus 4.2 minutes, 54% less traffic-risk exposure.** It skips Peachtree Place and Williams Street. It's honest when it can't help: both routes still cross Fifth Street, so it tells you to take care there."

**0:45 — Risk Tides (visualization).** Close the card, drag the timeline, press play.
"Risk isn't static. Scrub the day and watch corridors light up at the evening rush and late at night. Every frame uses one citywide 0–100 scale. This is 50,000 streets across all of Atlanta, re-scored for every hour and weather."

**1:10 — Why? (explainability).** Tap a glowing street, for example Fifth Street.
"Tap any street. The score splits exactly into its causes: vehicle crashes on this street, intersection complexity, block length. The bars always add up to the number. The sentence up top is built only from the model's evidence. When an LLM is connected (Grok first, then Groq, then Gemini), my validator throws out any sentence with a number that isn't in the evidence, or words like 'safe' or 'crime'."

**1:30 — Imagine this street *(after deploy, live site only)*.** On the same street sheet, tap "Imagine this street redesigned".
"For planners: Grok Imagine draws this street with the fixes its own risk factors point to, like crosswalks, curb extensions, and lighting. The prompt is built on the server, and the label says it's an illustration, not a real photo. Gemini checks the picture before it's shown and tells you which planned fixes it contains."

**1:40 — Honest ML (the credibility beat).** Open About.
"How do I know it works? I trained on 2020 to 2023 and tested on 2024 crashes it never saw. The 10% of Atlanta's streets it ranks highest held **74%** of 2024's pedestrian crashes. The City's High Injury Network got 54%. Past-crash counts alone got 50%. Random gets 12%. The confidence interval is on the card, and it tells you where the model is weak: rain adds a modest 12%, and it says exactly that."

**1:55 — Ask PathPro *(after deploy, live site only)*.** Tap "Ask about this street" and ask "Why is this street high?"
"If you want to go deeper, ask. Ask PathPro answers from the model card and the evidence for this street. Every answer is checked: if it has a number that isn't in the docs or the evidence, you never see it. Memory is off unless you turn it on, and Forget me deletes it."

**2:10 — City Pulse (scale).** Click City Pulse.
"Zoom out and City Pulse scores all 3,500 areas of Atlanta. The top 10% of areas held **three-quarters** of pedestrian crashes the next year."

**2:30 — Impact and close.**
"Atlanta's Vision Zero plan says a small share of streets causes most of the deaths. PathPro puts that knowledge in every walker's pocket, and in the city's hands. The traffic model uses no demographics and no crime data. Tap Preview walk and it speaks a heads-up 60 meters before each high-risk crossing. See the risks on your way, before you go."

## If something breaks

- **Wi-Fi down:** `?demo=1` runs fully offline after first load. As a last resort, use the phone hotspot.
- **LLM down or slow:** explanations fall back to the next provider, then to templates automatically, and nobody will notice.
- **Imagine or Ask unavailable:** skip those beats; the rest of the demo doesn't depend on them.
- **Laptop fails:** the phone has the live site.
