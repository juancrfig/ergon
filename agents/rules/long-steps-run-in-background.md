Rule:
A command expected to take more than 60 seconds (build, image build, deploy, capture run, full gate) starts as a background process and is read by status polls. Never wait on it in a foreground call, never chain `sleep` into status checks, and never retry a foreground call that timed out; read the background log instead. While it runs, the agent starts any independent work.

Prevents:
Foreground builds and deploys hit the tool timeout cap again and again. Long `sleep` status calls blocked a main session, and a worker sat in repeated fixed waits while independent work waited.

Enforce with:
Search the run for foreground builds, deploys and captures. Each one must show a background start, then polls that return quickly. A foreground timeout followed by the same command again fails this rule.
