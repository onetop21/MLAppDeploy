import sys
import gettext


def translator(language=None, fallback=True):
    # Languages = ko_KR or eu_US
    t = gettext.translation('mlad.cli', 'locale', languages=[language] if language else None, fallback=fallback)
    return t.gettext


sys.modules[__name__] = translator

if __name__ == '__main__':
    _ = translator()
    print(_('Hello World'))
