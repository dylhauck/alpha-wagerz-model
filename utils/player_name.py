import re
import unicodedata

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_player_name(name) -> str:
    if not name:
        return ""

    value = (
        unicodedata.normalize("NFKD", str(name))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    value = value.replace(".", " ").replace("'", "").replace("’", "").replace("-", " ")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return " ".join(part for part in value.split() if part not in SUFFIXES)


def player_last_name(name) -> str:
    parts = normalize_player_name(name).split()
    return parts[-1] if parts else ""
