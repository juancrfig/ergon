# Profiles

One folder per node agent. `config.yaml` is copied verbatim into the Hermes profile; `skills/*.md` are read by the
runner and placed in the prompt, one per request type. A change here is a change to an agent's context: it reaches
the agent only through a commit the human approves (ADR 0002, 0006). Memory stays off.
