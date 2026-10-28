# Project instructions

Read [AI_START_HERE.md](AI_START_HERE.md) before using the memory workflow.
It defines the shared entry point for all tools, not permission to read a whole
vault, run commands, upload notes or activate automation.

For explicitly requested code maintenance, read README.md and the affected
scripts/tests. Use fictional temporary fixtures, preserve user changes, run
`python -m unittest discover -s tests -v` and
`python scripts/check_public_content.py`. No automatic Skill loading, model
connections, plugin installation, publishing or payment.
