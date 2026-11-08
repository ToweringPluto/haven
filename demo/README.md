# Haven: demo and challenge submissions

Haven (Housing And Visibility Edinburgh Network) helps Edinburgh renters see what a listing doesn't show before they commit: the true monthly cost, whether the home and its routes work for them, and possible problems such as damp or mould that photos hide.

This folder explains how Haven fits each HackTheBurgh 2026 challenge track we're entering, and how we used each partner technology.

**Presentation:** [haven-presentation.pptx](haven-presentation.pptx): the pitch deck (9 slides: problem, why it matters, approach, architecture, demo video, next steps, references, team). **Demo video:** [docs/media/haven-demo.mp4](../docs/media/haven-demo.mp4).

## Challenge tracks

| Track | Brief | Our doc |
| --- | --- | --- |
| **G-Research**: Make the invisible visible | Choose something hard to observe; show what data is hidden, how to find it and what to do with it | [g-research/README.md](g-research/README.md) |
| **HRT**: Best Use of Data for Predictions & Decision Making | Combine diverse inputs into signals, then turn them into automated decisions | [hrt/README.md](hrt/README.md) |
| **Bank of Scotland**: Smart Cost of Living | Help customers navigate trade-offs and make better decisions about money and everyday life | [bank-of-scotland/README.md](bank-of-scotland/README.md) |

## Technologies

| Technology | What it does in Haven | Doc |
| --- | --- | --- |
| **Auth0** | Sign-in for features that store data or cost money to run: photo screening, uploads, saved reports and homes | [auth0.md](auth0.md) |
| **Google Gemini API** | Screens photos for possible damp, mould and entrance steps; reads reports aloud (text-to-speech); optionally rewords report sentences | [google-gemini-api.md](google-gemini-api.md) |
| **Tiger Cloud** (Postgres + TimescaleDB) | Stores profiles, reports, upload records and saved homes; holds Lothian rent statistics (2010 to 2025) as a hypertable | [tiger-cloud.md](tiger-cloud.md) |

## The demo in three minutes

1. **Create a renter profile**: budget, priorities and any access needs (for example step-free entry).
2. **Explore the map**: 48 illustrative Edinburgh homes. Switch the map's colour coding between total cost against budget, heating cost risk, step-free entrance, lift, walk to transport and travel time.
3. **Open a property**: see the true monthly cost (rent + council tax + modelled energy) against the budget, and the rent compared with Lothian rent statistics.
4. **Check suitability**: each rule result says *meets*, *concern* or *unknown*, with the facts and sources behind it.
5. **Screen a photo** (signed in): Gemini rates possible damp, mould and entrance steps, after a local photo-quality check.
6. **Read the report**: what works, what may not, and what to check before signing, every sentence tied to its evidence.

## Ground rules we kept throughout

- **Evidence before prediction.** We calculate what can be calculated, use rules for what can be checked, and only use a model for what can't be observed any other way.
- **"Insufficient evidence" is a valid answer.** Every check and every model output can say it doesn't know.
- **Possibilities, not diagnoses.** Haven says "possible mould visible, inspect before signing", never "this flat has mould".
- **No hidden score.** Haven never collapses a home into one number. It shows the evidence and the uncertainty.
