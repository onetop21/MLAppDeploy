import sys

# PACKMAN FILENAME
FORMAT = '''COPY {SRC} .depends/apk.list
RUN cat apk.list | xargs apk add'''

sys.modules[__name__] = FORMAT
