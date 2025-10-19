# HeritageNet Example

This repo builds **HeritageNet**, a structured knowledge graph from historical medical texts, using large language models and Neo4j.

## Files

- **main.py** — Loads text, extracts graph data, and writes it to Neo4j  
- **KGAgents.py** — Defines the KnowledgeGraphAgent using the camel-ai library  
- **sample_input.txt** — Contains 20 randomly sampled pages from:  
  *Traité de la moelle épinière et de ses maladies*, Ollivier (1827)  
- **output_viz.html** — Optional visualization of the resulting graph

## Installation

```bash
pip install "camel-ai[all]==0.2.16" neo4j
export GROQ_API_KEY="your_key"
```

## Usage

Configure Neo4j credentials in main.py, then run:

```bash

python main.py
```

## HeritageNet Taxonomy

HeritageNet captures medical knowledge as reported in traditional and early modern texts, without modern reinterpretation.

### Core Evidence Entities

**ClinicalObservation**  
Historical signs, symptoms, or disease states 
*e.g.* “congestions sanguines rachidiennes”

**TherapeuticOutcome**  
Documented effects of treatments (including failures or side effects)  
*e.g.* convulsions 

**ContextualFactor**  
Environmental, demographic, or behavioral correlates  
*e.g.* suppressed sweat, lochia

**MechanisticConcept**  
Explanatory theories proposed at the time  
*e.g.* spinal vein congestion causes motor paralysis

**TherapeuticApproach**  
Treatments and their preparation/administration  
*e.g.* hydrocyanic acid on vesicatory wounds

**SourceText**  
Bibliographic origin of the knowledge  
*e.g.* Ollivier’s 1824 treatise

### Evidence Relationships

- `co_occurs_with`: Joint appearance of entities  
- `preceded_by`, `followed_by`: Temporal flow  
- `modified_by`: Changes due to external/internal factors  
- `responds_to`: Symptom change after treatment  
- `associated_with`: Loose historical association  
- `results_in`: Direct effects  
- `described_in`: Tied to source text  
- `contradicts`, `corroborates`: Consistency/conflict between items  

Each relation can include metadata qualifiers to preserve historical ambiguity.

---

### Project

This toy example is part of Chronos. Chronos mines overlooked historical texts to generate novel, testable hypotheses using LLMs and structured graph reasoning.
