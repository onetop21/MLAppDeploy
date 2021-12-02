import sys

# PACKMAN FILENAME
FORMAT = '''COPY {SRC} .depends/yum.list
RUN cat yum.list | xargs yum -y install'''

sys.modules[__name__] = FORMAT
