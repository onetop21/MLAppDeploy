import sys

FORMAT='''# MLAppDeploy Dockerfile
FROM {BASE}
MAINTAINER {AUTHOR}

# Environments
{ENVS}

# Working directory
WORKDIR /workspace

# Requires
{REQUIRES}

# Copy projects
COPY . .

# Entrypoint
CMD {COMMAND}

'''

sys.modules[__name__] = FORMAT
