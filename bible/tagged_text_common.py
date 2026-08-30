import re

# Matches the reference column, e.g. "Mat.1.1#01=NKO" or "Gen.1.1#01=L",
# and also the form with a parenthetical alternate reference used when
# Hebrew versification differs from English, e.g. "Psa.3.1(3.2)#01=L" --
# the primary (pre-parenthesis) reference is the English/NRSV-style
# numbering, which is what we match our KJV verses against.
REF_RE = re.compile(r'^([A-Za-z0-9]{2,4})\.(\d+)\.(\d+)(?:\([^)]*\))?#(\d+)=')

# Strips a leading zero-padded Strong's number to our lexicon's format,
# e.g. "G0025" -> "G25" or "H7225G" -> "H7225", dropping any trailing
# instance/disambiguation/edition suffix like "_A" or a letter.
STRONGS_RE = re.compile(r'^\{?([GH])0*(\d+)')


def normalize_strongs(raw):
    if not raw:
        return ''
    m = STRONGS_RE.match(raw.strip())
    if not m:
        return ''
    return f"{m.group(1)}{m.group(2)}"
