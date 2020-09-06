import sys

FORMAT='''# MLAppDeploy Dockerfile
FROM {BASE}
MAINTAINER {AUTHOR}

# Environments
{ENVS}

# Working directory
WORKDIR /workspace

# Pre Scripts
RUN {PRESCRIPTS}

# Requires
{REQUIRES}

# Copy projects
COPY . .

#Post Scripts
RUN {POSTSCRIPTS}

# Entrypoint
CMD {COMMAND}

'''

sys.modules[__name__] = FORMAT
