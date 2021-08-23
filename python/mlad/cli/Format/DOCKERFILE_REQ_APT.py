import sys

# PACKMAN FILENAME
FORMAT = '''COPY {SRC} .depends/apt.list
RUN xargs -a .depends/apt.list -I % sh -c "apt install -y %"'''

sys.modules[__name__] = FORMAT
