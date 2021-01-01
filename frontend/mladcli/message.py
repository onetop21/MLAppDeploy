import sys
import gettext

keys

def translator(language=None, fallback=True):
    # Languages = ko_KR or eu_US
    t = gettext.translation('mladcli', 'locale', languages=language, fallback=fallback)
    return t.gettext

sys.modules[__name__] = translator
