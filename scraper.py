import requests
import pandas as pd
import re
import os
import json


# =========================================================
# CONFIG
# =========================================================

OUTPUT_FILE = "hanbeego_vocab.xlsx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}


# =========================================================
# TỪ LOẠI
# =========================================================

POS_MAP = {
    "noun": "Danh từ",
    "verb": "Động từ",
    "adjective": "Tính từ",
    "pronoun": "Đại từ",
    "adverb": "Trạng từ",
    "particle": "Trợ từ",
    "measure_word": "Lượng từ",
    "classifier": "Lượng từ",
    "conjunction": "Liên từ",
    "interjection": "Thán từ",
    "preposition": "Giới từ",
    "numeral": "Số từ",
    "determiner": "Định từ",
    "phrase": "Cụm từ",
    "greeting": "Chào hỏi",
    "auxiliary": "Trợ động từ",
    "adverbial": "Trạng từ",
}


# =========================================================
# REQUEST
# =========================================================

def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text


# =========================================================
# HELPERS
# =========================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)

    value = re.sub(
        r"\s+",
        " ",
        value
    ).strip()

    return value


def is_hanzi(value):
    if not value:
        return False

    value = str(value).strip()

    return bool(
        re.fullmatch(
            r"[\u3400-\u4DBF\u4E00-\u9FFF]+",
            value
        )
    )


def normalize_rsc(text):
    """
    Next.js RSC có thể escape JSON nhiều lớp.
    Chuẩn hóa các kiểu phổ biến:

        \\"  -> "
        \\u0022 -> "
        \\/ -> /
        \\\\ -> \\

    Không parse toàn bộ HTML thành JSON vì RSC không phải
    một JSON document duy nhất.
    """

    result = text

    # Decode Unicode quote escape trước.
    result = result.replace(
        "\\u0022",
        '"'
    )

    result = result.replace(
        "\\u0027",
        "'"
    )

    # Có thể có nhiều lớp escape.
    for _ in range(4):
        new_result = result.replace(
            '\\"',
            '"'
        )

        if new_result == result:
            break

        result = new_result

    return result


# =========================================================
# FIND VOCAB OBJECTS DIRECTLY
#
# KHÔNG còn phụ thuộc vào:
#
#     "vocabs":[...]
#
# vì Next.js RSC có thể chia/escape dữ liệu khiến việc tìm
# nguyên array thất bại.
#
# Thay vào đó tìm trực tiếp từng object có:
#
#     id = v_HSKx_xxxx
#     hanzi
#     pinyin
#     partOfSpeech
#     meanings
#
# Đây vẫn đúng flow:
#
# HTML
#   ↓
# Next.js embedded data
#   ↓
# vocabulary object
#   ↓
# id / hanzi / pinyin / partOfSpeech / meanings
#   ↓
# DataFrame
# =========================================================

def extract_vocab_objects(html):

    text = normalize_rsc(html)

    results = []

    # -----------------------------------------------------
    # Pattern chính.
    #
    # Không giới hạn độ dài Hanzi/Pinyin.
    # -----------------------------------------------------

    pattern = re.compile(
        r'"id"\s*:\s*"(?P<id>v_HSK\d+_\d+)"'
        r'.{0,5000}?'
        r'"hanzi"\s*:\s*"(?P<hanzi>.*?)"'
        r'.{0,1000}?'
        r'"pinyin"\s*:\s*"(?P<pinyin>.*?)"'
        r'.{0,3000}?'
        r'"partOfSpeech"\s*:\s*\[(?P<pos>.*?)\]'
        r'.{0,3000}?'
        r'"meanings"\s*:\s*(?P<meanings>\[)',
        re.DOTALL
    )

    for match in pattern.finditer(text):

        item_id = match.group("id")
        hanzi = clean_text(
            match.group("hanzi")
        )
        pinyin = clean_text(
            match.group("pinyin")
        )

        if not is_hanzi(hanzi):
            continue

        # -------------------------------------------------
        # Lấy POS.
        # -------------------------------------------------

        raw_pos = match.group(
            "pos"
        )

        pos_values = re.findall(
            r'"([^"]+)"',
            raw_pos
        )

        # -------------------------------------------------
        # Tìm phần meanings đầy đủ bằng bracket matching.
        # Không dùng .*? vì meanings có thể chứa object lồng nhau.
        # -------------------------------------------------

        meanings_start = match.end(
            "meanings"
        ) - 1

        meanings_raw = extract_balanced_json(
            text,
            meanings_start
        )

        meanings = []

        if meanings_raw:

            try:
                meanings = json.loads(
                    meanings_raw
                )
            except Exception:
                # Thử decode thêm một lớp.
                try:
                    meanings = json.loads(
                        meanings_raw.replace(
                            '\\"',
                            '"'
                        )
                    )
                except Exception:
                    meanings = []

        results.append({
            "id": item_id,
            "hanzi": hanzi,
            "pinyin": pinyin,
            "partOfSpeech": pos_values,
            "meanings": meanings
        })

    # -----------------------------------------------------
    # Nếu pattern trên không bắt được, dùng pattern ngược:
    # tìm hanzi trước rồi dò id gần đó.
    # -----------------------------------------------------

    if not results:

        fallback_pattern = re.compile(
            r'"hanzi"\s*:\s*"(?P<hanzi>.*?)"'
            r'.{0,1000}?'
            r'"pinyin"\s*:\s*"(?P<pinyin>.*?)"'
            r'.{0,3000}?'
            r'"partOfSpeech"\s*:\s*\[(?P<pos>.*?)\]',
            re.DOTALL
        )

        for match in fallback_pattern.finditer(text):

            hanzi = clean_text(
                match.group("hanzi")
            )

            if not is_hanzi(hanzi):
                continue

            pinyin = clean_text(
                match.group("pinyin")
            )

            raw_pos = match.group(
                "pos"
            )

            pos_values = re.findall(
                r'"([^"]+)"',
                raw_pos
            )

            results.append({
                "id": "",
                "hanzi": hanzi,
                "pinyin": pinyin,
                "partOfSpeech": pos_values,
                "meanings": []
            })

    return results


# =========================================================
# BALANCED JSON ARRAY
# =========================================================

def extract_balanced_json(text, start):
    """
    start phải trỏ vào '['.

    Tìm đúng dấu ']' tương ứng, có xử lý:
    - nested []
    - nested {}
    - string
    - escaped quote
    """

    if (
        start < 0
        or start >= len(text)
        or text[start] != "["
    ):
        return None

    square_depth = 0
    curly_depth = 0

    in_string = False
    escaped = False

    for i in range(
        start,
        len(text)
    ):

        char = text[i]

        if in_string:

            if escaped:
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char == '"':
                in_string = False

            continue

        if char == '"':
            in_string = True
            continue

        if char == "[":
            square_depth += 1

        elif char == "]":
            square_depth -= 1

            if (
                square_depth == 0
                and curly_depth == 0
            ):
                return text[
                    start:i + 1
                ]

        elif char == "{":
            curly_depth += 1

        elif char == "}":
            curly_depth -= 1

    return None


# =========================================================
# MEANINGS
# =========================================================

def parse_meanings(meanings):

    if not isinstance(
        meanings,
        list
    ):
        return ""

    values = []

    for meaning in meanings:

        if not isinstance(
            meaning,
            dict
        ):
            continue

        vi = clean_text(
            meaning.get(
                "vi",
                ""
            )
        )

        note = clean_text(
            meaning.get(
                "note",
                ""
            )
        )

        if vi and note:
            value = (
                f"{vi} ({note})"
            )
        else:
            value = vi or note

        if value:
            values.append(value)

    if not values:
        return ""

    if len(values) == 1:
        return values[0]

    return "; ".join(
        f"{index}. {value}"
        for index, value in enumerate(
            values,
            start=1
        )
    )


# =========================================================
# PARSE ONE OBJECT
# =========================================================

def parse_vocab_item(item):

    if not isinstance(
        item,
        dict
    ):
        return None

    item_id = clean_text(
        item.get(
            "id",
            ""
        )
    )

    # Nếu có ID thì phải là vocabulary ID.
    if item_id and not re.fullmatch(
        r"v_HSK\d+_\d+",
        item_id
    ):
        return None

    hanzi = clean_text(
        item.get(
            "hanzi",
            ""
        )
    )

    pinyin = clean_text(
        item.get(
            "pinyin",
            ""
        )
    )

    if not hanzi:
        return None

    if not is_hanzi(hanzi):
        return None

    # POS
    raw_pos = item.get(
        "partOfSpeech",
        []
    )

    if not isinstance(
        raw_pos,
        list
    ):
        raw_pos = [
            raw_pos
        ]

    pos_values = []

    for pos in raw_pos:

        pos = clean_text(
            pos
        )

        if not pos:
            continue

        pos = POS_MAP.get(
            pos,
            pos
        )

        if pos not in pos_values:
            pos_values.append(
                pos
            )

    pos = ", ".join(
        pos_values
    )

    # Meaning
    meaning = parse_meanings(
        item.get(
            "meanings",
            []
        )
    )

    return {
        "Hanzi": hanzi,
        "Pinyin": pinyin,
        "Từ loại": pos,
        "Nghĩa": meaning
    }


# =========================================================
# DEDUPLICATE
# =========================================================

def deduplicate_vocab(data):

    result = []
    seen = set()

    for item in data:

        if not item:
            continue

        hanzi = clean_text(
            item.get(
                "Hanzi",
                ""
            )
        )

        pinyin = clean_text(
            item.get(
                "Pinyin",
                ""
            )
        )

        if not hanzi:
            continue

        key = (
            hanzi,
            pinyin.casefold()
        )

        if key in seen:
            continue

        seen.add(key)

        result.append({
            "Hanzi": hanzi,
            "Pinyin": pinyin,
            "Từ loại": clean_text(
                item.get(
                    "Từ loại",
                    ""
                )
            ),
            "Nghĩa": clean_text(
                item.get(
                    "Nghĩa",
                    ""
                )
            )
        })

    return result


# =========================================================
# SCRAPE
# =========================================================

def scrape_vocab(url):

    html = get_page(url)

    raw_objects = extract_vocab_objects(
        html
    )

    if not raw_objects:

        raise Exception(
            "Không tìm thấy dữ liệu vocabulary "
            "trong Next.js embedded JSON."
        )

    results = []

    for item in raw_objects:

        parsed = parse_vocab_item(
            item
        )

        if parsed:
            results.append(
                parsed
            )

    results = deduplicate_vocab(
        results
    )

    if not results:

        raise Exception(
            "Đã tìm thấy embedded data nhưng "
            "không có vocabulary hợp lệ."
        )

    return results


# =========================================================
# EXCEL
# =========================================================

def load_existing():

    if not os.path.exists(
        OUTPUT_FILE
    ):
        return pd.DataFrame(
            columns=[
                "STT",
                "Hanzi",
                "Pinyin",
                "Từ loại",
                "Nghĩa"
            ]
        )

    try:

        return pd.read_excel(
            OUTPUT_FILE
        )

    except Exception:

        return pd.DataFrame(
            columns=[
                "STT",
                "Hanzi",
                "Pinyin",
                "Từ loại",
                "Nghĩa"
            ]
        )


def save_excel(
    old_df,
    new_data
):

    new_df = pd.DataFrame(
        new_data,
        columns=[
            "Hanzi",
            "Pinyin",
            "Từ loại",
            "Nghĩa"
        ]
    )

    if not old_df.empty:

        old_df = old_df.drop(
            columns=[
                "STT"
            ],
            errors="ignore"
        )

        combined = pd.concat(
            [
                old_df,
                new_df
            ],
            ignore_index=True
        )

    else:

        combined = new_df.copy()

    required = [
        "Hanzi",
        "Pinyin",
        "Từ loại",
        "Nghĩa"
    ]

    for column in required:

        if column not in combined.columns:
            combined[column] = ""

    combined = combined[
        required
    ]

    for column in required:

        combined[column] = (
            combined[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    combined = combined.drop_duplicates(
        subset=[
            "Hanzi",
            "Pinyin"
        ],
        keep="first"
    ).reset_index(
        drop=True
    )

    combined.insert(
        0,
        "STT",
        range(
            1,
            len(combined) + 1
        )
    )

    combined = combined[
        [
            "STT",
            "Hanzi",
            "Pinyin",
            "Từ loại",
            "Nghĩa"
        ]
    ]

    combined.to_excel(
        OUTPUT_FILE,
        index=False
    )

    return (
        len(new_df),
        len(combined)
    )