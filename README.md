# Haven — Housing And Visibility Edinburgh Network

Haven helps Edinburgh renters understand whether a property is affordable, accessible, practical and worth investigating before they commit to living there.

> **Project scope:** Haven is a prototype and decision-support tool. It is not a legal, safety, accessibility or compliance certification system. Its assessments are indicative and should be checked against the property in person and with appropriate professional advice.

## The problem: important housing information is invisible

A rental listing usually shows the asking rent, number of bedrooms and a location. It rarely shows what a property will actually cost to live in, whether the building and surrounding routes work for a particular renter, or whether the available photographs and documents contain warning signs.

This makes housing decisions difficult because the information that matters most is often:

- **Hidden in the true cost:** council tax, energy and recurring costs can make an apparently affordable property unaffordable.
- **Personal and contextual:** a step, unreliable lift or inaccessible route may matter greatly to one renter and not at all to another.
- **Distributed across sources:** transport, amenities, property details and public information are not usually presented together.
- **Difficult to observe:** possible damp, mould, access barriers or missing evidence may only become apparent in photographs, floor plans or documents.

Haven makes these factors more visible by bringing together structured property data, renter requirements, location data and uploaded evidence. It turns them into a transparent assessment of what appears suitable, what may be a concern and what the renter should investigate next.

## How Haven uses data for prediction and decision-making

Haven uses different methods for different kinds of decisions. The method is chosen to keep results explainable and to avoid asking a machine-learning model to make a judgement that can be calculated directly.

| Question | Data and method | Result |
| --- | --- | --- |
| What will the property cost each month? | Rent, council tax, estimated energy and recurring costs processed with deterministic calculations | Estimated monthly expenditure and comparison with the renter's budget |
| Can the property meet stated requirements? | Property facts, location data and explicit rules | Checks for barriers such as steps, lift availability, route distance and transport access |
| What may be difficult to observe? | Images, floor plans and documents analysed with carefully scoped ML classifiers and extraction tools | Potential concerns, missing evidence and confidence levels |
| What does the evidence mean for this renter? | Structured outputs combined with the renter's priorities | A plain-language explanation with reasons and suggested next steps |

Machine learning is useful where the evidence is difficult to observe directly. Possible classifiers could identify visual signals such as possible damp or mould, an entrance step or an apparent access barrier. A model output is a signal, not a fact:

```text
Possible damp or mould: 0.78 confidence
Possible entrance step: 0.94 confidence
Insufficient image evidence: true
```

Haven should report this as **“possible damp detected; inspect before signing”**, not **“this property has damp.”** A model must be able to return *insufficient evidence*, and its output should retain the source, confidence and uncertainty. An LLM may explain structured results in plain language, but it must not invent a property score or unsupported conclusion from a description.

The final recommendation supports the renter's judgement. It does not reject applicants, make decisions about people, or certify that a property is safe, accessible or compliant.

## How Haven makes the invisible visible

Haven's central question is:

> What does a renter need to know that a listing does not normally reveal, and what evidence can help reveal it?

The system investigates this gap by:

1. **Collecting structured property information** such as rent, council tax band, EPC rating, floor, lift availability and entrance details.
2. **Combining it with context** such as transport links, routes to essential destinations and the renter's budget, priorities and accessibility requirements.
3. **Gathering additional evidence** from uploaded photographs, floor plans and property documents.
4. **Applying calculations, rules and scoped ML models** to expose costs, barriers, potential concerns and missing information.
5. **Presenting the evidence and uncertainty** in an actionable report rather than hiding it behind an unexplained score.

This approach can also incorporate relevant public data, provided the source, date and limitations are clear. The goal is not to claim that data can reveal everything about a property. The goal is to show what is known, what has been inferred, what remains uncertain and what the renter should check.

## Core capabilities

### 1. Property profile

The user selects a property or enters its details:

- Rent and council tax band
- EPC rating
- Floor and lift availability
- Entrance steps and other access information
- Available source information

### 2. True cost calculator

Haven estimates the real recurring cost of living there:

- Monthly rent
- Council tax
- Estimated energy costs
- Other relevant recurring costs

The estimated total is compared with the renter's stated budget. Estimates are labelled as estimates, not guarantees.

### 3. Personalised suitability assessment

Haven evaluates:

- Property accessibility
- Routes to transport and essential destinations
- Location and transport suitability
- Potential barriers in relation to the renter's requirements

It explains why a property may or may not suit this particular renter. A property is not simply “good” or “bad”: it may be suitable for one person and unsuitable for another.

For example:

- A wheelchair user may prioritise step-free access and lift reliability.
- A student may prioritise rent, transport and proximity to university.
- A family may prioritise space, heating costs and nearby schools.
- Someone on a tight budget may prioritise total monthly expenditure.

### 4. AI property screening

The user can upload a photograph, floor plan or property document. Screening may flag:

- Possible damp or mould
- Possible access barriers
- Missing safety or property information
- Features that require further inspection

These are potential signals for investigation, not diagnoses or certifications.

## Example user journey

1. **Create a renter profile** — enter a monthly budget, transport needs, priorities and optional accessibility requirements.
2. **Choose a property** — select one of the example Edinburgh rental properties or enter property details.
3. **Calculate the true cost** — estimate monthly expenditure and compare it with the budget.
4. **Assess suitability** — evaluate the building, surrounding routes and the renter's requirements.
5. **Screen for potential issues** — upload a photograph or document and review possible concerns and missing evidence.
6. **Get a recommendation** — receive a report that explains what works, what may be unsuitable, what could be expensive and what needs checking before signing.

### Illustrative report

**Property Suitability Report**

*Illustrative output, not a certified assessment*

- Estimated monthly cost: £1,150
- Stated budget: £1,200
- Potential accessibility barrier: entrance steps
- Property concern: possible damp visible in an uploaded photograph
- Missing information: lift maintenance history

**Recommendation:** investigate the entrance and property condition before committing. The estimated cost is within the stated budget, but suitability is not yet established.

## Proposed technical approach

Haven is designed as a hybrid decision-support system:

| Component | Approach | Output |
| --- | --- | --- |
| True cost | Deterministic calculations | Estimated monthly expenditure |
| Explicit requirements | Rules and structured data | Transparent checks and reasons |
| Property screening | Computer vision and document extraction/classification | Potential concerns, missing evidence and confidence |
| Explanation | AI-generated natural-language summary grounded in structured results | Personalised report and next steps |

The important principle is **evidence before prediction**. Where a result can be calculated or checked with a clear rule, Haven should do that directly. ML is reserved for patterns that are hard to observe, and every prediction should be presented with its evidence, confidence and limitations.

## Status and limitations

Haven is a prototype / demonstration of this concept. Data sources, model performance, estimated costs and property evidence may be incomplete or inaccurate. Image and document analysis can miss issues or produce false positives. Users should verify important information with the landlord or agent, inspect the property, and seek professional advice where necessary.
