# Profiles

One folder per node agent, holding only `skills/*.md`: the runner places one in the prompt per request type. A change
here is a change to an agent's context: it reaches the agent only through a commit the human approves (ADR 0002).

The Hermes profile of the same name holds only the model and credentials, set by hand. Nothing in it reaches the
model (ADR 0010).
