import sys

# PACKMAN FILENAME
FORMAT = '''COPY {SRC} .depends/pip.list
RUN pip install -r .depends/pip.list'''

sys.modules[__name__] = FORMAT
