import re


_PHRASE_TRANSLATIONS = {
    "нидерланды": "netherlands",
    "германия": "germany",
    "сша": "usa",
    "соединенные штаты": "usa",
    "соединённые штаты": "usa",
    "великобритания": "united_kingdom",
    "южная корея": "south_korea",
    "северная корея": "north_korea",
    "новая зеландия": "new_zealand",
    "саудовская аравия": "saudi_arabia",
    "объединенные арабские эмираты": "uae",
    "объединённые арабские эмираты": "uae",
}

_TOKEN_TRANSLATIONS = {
    "нидерланды": "netherlands",
    "германия": "germany",
    "сша": "usa",
    "россия": "russia",
    "франция": "france",
    "италия": "italy",
    "испания": "spain",
    "польша": "poland",
    "турция": "turkey",
    "канада": "canada",
    "япония": "japan",
    "китай": "china",
    "индия": "india",
    "швейцария": "switzerland",
    "швеция": "sweden",
    "норвегия": "norway",
    "финляндия": "finland",
    "австрия": "austria",
    "бельгия": "belgium",
    "чехия": "czechia",
    "португалия": "portugal",
    "австралия": "australia",
    "корея": "korea",
    "южная": "south",
    "северная": "north",
    "новая": "new",
    "великобритания": "united_kingdom",
    "ирландия": "ireland",
    "сингапур": "singapore",
}

_COUNTRY_CODE_PREFIXES = {"nl", "de", "us", "ru", "fr", "it", "es", "pl", "tr", "uk", "gb"}

_CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def _transliterate_token(token: str) -> str:
    result = []
    for char in token.lower():
        if char in _CYRILLIC_TO_LATIN:
            result.append(_CYRILLIC_TO_LATIN[char])
        elif re.match(r"[a-z0-9]", char):
            result.append(char)
    return "".join(result)


def generate_config_filename(location_name: str) -> str:
    normalized = re.sub(r"[\U00010000-\U0010FFFF]", " ", location_name or "")
    tokens = re.findall(r"[A-Za-z0-9А-Яа-яЁё]+", normalized)
    lowered_tokens = [token.lower() for token in tokens if token]

    if lowered_tokens and lowered_tokens[0] in _COUNTRY_CODE_PREFIXES and len(lowered_tokens) > 1:
        lowered_tokens = lowered_tokens[1:]

    phrase = " ".join(lowered_tokens).strip()
    if phrase in _PHRASE_TRANSLATIONS:
        slug = _PHRASE_TRANSLATIONS[phrase]
        return f"{slug}_exvpn.conf"

    translated_tokens: list[str] = []
    idx = 0
    while idx < len(lowered_tokens):
        if idx + 1 < len(lowered_tokens):
            pair = f"{lowered_tokens[idx]} {lowered_tokens[idx + 1]}"
            if pair in _PHRASE_TRANSLATIONS:
                translated_tokens.append(_PHRASE_TRANSLATIONS[pair])
                idx += 2
                continue

        token = lowered_tokens[idx]
        if token in _TOKEN_TRANSLATIONS:
            translated = _TOKEN_TRANSLATIONS[token]
        else:
            translated = _transliterate_token(token)

        if translated:
            translated_tokens.append(translated)
        idx += 1

    slug = "_".join(translated_tokens)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        slug = "config"

    return f"{slug}_exvpn.conf"