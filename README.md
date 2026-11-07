# Haven- Housing And Visibility Edinburgh Network

Haven helps Edinburgh renters understand whether a property is affordable, accessible, suitable and safe before they commit to living there.

## Look beyond the listing

Haven turns property information into a personalised assessment of whether a home is right for the person considering it.

Finding a flat in Edinburgh is difficult. But finding somewhere that is genuinely right for you is even harder. A property listing might tell you the rent, number of bedrooms and location. It rarely tells you what it will actually cost to live there, whether you can access the building, whether the surrounding streets meet your needs, or whether there are potential problems you should investigate before signing.

That is why we are building Haven.

Haven is an AI-powered rental suitability platform that helps Edinburgh renters make better-informed housing decisions. You tell Haven what matters to you. It assesses a property's real monthly costs, accessibility, surrounding neighbourhood and potential property concerns.

Instead of simply showing you a listing, Haven produces a personalised assessment explaining what works, what doesn't and what you should investigate before committing.

Because finding a home is not just about finding somewhere available. It is about finding somewhere you can afford, access and feel secure living in.

### Core questions Haven answers

- Affordability: What will it really cost me?
- Accessibility: Can I use the property and its surroundings?
- Property screening: Are there potential issues I should investigate?
- Location suitability: Can I access the places I need?

The key principle is personalisation. A property is not simply good or bad. It may be suitable for one renter and unsuitable for another.

Examples:

- A wheelchair user may prioritise step-free access and lift reliability.
- A student may prioritise rent, transport and proximity to university.
- A family may prioritise space, heating costs and nearby schools.
- Someone on a tight budget may prioritise total monthly expenditure.

Haven lets people assess properties against their own priorities.

---


### 1. Property profile
The user selects a property or enters its details.

Show:

- Rent and council tax band
- EPC rating
- Floor and lift availability
- Entrance steps
- Available property information

### 2. True cost calculator
Estimate what living there will actually cost.

Include:

- Monthly rent
- Council tax
- Estimated energy costs
- Other relevant recurring costs

Compare the estimated total against the renter's stated budget.

### 3. Suitability assessment
Evaluate:

- Property accessibility
- Routes to transport and essentials
- Location and transport suitability
- Potential barriers based on the user's requirements

Show why the property may or may not suit them.

### 4. AI property screening
Upload a photograph, floor plan or property document.

AI flags potential concerns such as:

- Visible damp or mould
- Possible access barriers
- Missing safety or property information
- Features that require further inspection

---

## User journey
1. Create a renter profile
   - The user enters their monthly budget, transport needs and priorities.
   - Accessibility requirements are optional and customisable.

2. Choose a property
   - The user selects one of a small set of example Edinburgh rental properties.

3. Calculate the real cost
   - Haven estimates monthly expenditure and compares it with the budget.

4. Assess suitability
   - Haven evaluates the building, surrounding routes and the user's requirements.

5. Screen for potential issues
   - The user uploads a property photograph or document.
   - AI identifies visible concerns and missing information.

6. Get a recommendation
   - Haven produces a personalised report explaining:
     - What works well
     - What might be unsuitable
     - What could be expensive
     - What needs checking before signing

### Final result

Property Suitability Report

Illustrative output, not a certified assessment
For example:
- Estimated monthly cost: £1,150
- Budget: £1,200
- Potential accessibility barrier: entrance steps
- Property concern: possible damp visible in uploaded photograph
- Missing information: lift maintenance history

Recommendation: investigate the entrance and property condition before committing. The estimated cost is within the stated budget, but suitability is not yet established.

This is a complete demonstration of Haven's value: it turns fragmented property information into an actionable decision.

---

## How the AI should work

Use three different types of intelligence.

| Component | Technology approach | Output |
| --- | --- | --- |
| True Cost | Deterministic calculations | Estimated monthly expenditure |
| Suitability | Rules + personalised AI explanation | Property fit and reasons |
| Property screening | Computer vision + document extraction | Potential concerns and missing evidence |

Important: do not let an LLM invent a property score from a description. Use structured data and rules to calculate the results, then use AI to explain them in plain language.

For the compliance-related element, call it AI Property Screening rather than an automated compliance certification system.