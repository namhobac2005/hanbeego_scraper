import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
import os


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

POS_LIST = [
    "Danh từ",
    "Động từ",
    "Tính từ",
    "Đại từ",
    "Trạng từ",
    "Trợ từ",
    "Lượng từ",
    "Liên từ",
    "Thán từ",
    "Giới từ",
    "Phó từ",
    "Số từ",
    "Định từ",
]


# =========================================================
# GET PAGE
# =========================================================

def get_page(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


# =========================================================
# CHECK HANZI
# =========================================================

def is_hanzi(text):

    if not text:
        return False

    text = text.strip()

    return bool(
        re.fullmatch(
            r"[\u3400-\u4DBF\u4E00-\u9FFF]+",
            text
        )
    )


# =========================================================
# CHECK VOCAB START
#
# Ví dụ:
#
# 01
# 不
#
# 02
# 好
#
# 10
# 学生
#
# Chỉ những số này mới là STT từ.
# =========================================================

def is_vocab_start(lines, index):

    if index >= len(lines):
        return False

    current = lines[index].strip()

    if not re.fullmatch(
        r"\d{2}",
        current
    ):
        return False

    # Phải có Hanzi ngay phía sau
    if index + 1 >= len(lines):
        return False

    return is_hanzi(
        lines[index + 1]
    )


# =========================================================
# CLEAN MEANING
# =========================================================

def clean_meaning(parts):

    if not parts:
        return ""

    result = []

    for part in parts:

        part = part.strip()

        if not part:
            continue

        # Bỏ dấu *
        if part == "*":
            continue

        # Bỏ số thứ tự nghĩa
        if re.fullmatch(
            r"\d+",
            part
        ):
            continue

        # Bỏ dấu chấm đứng riêng
        if part in [".", "．"]:
            continue

        result.append(part)

    # Ghép lại
    text = " ".join(result)

    # Xử lý khoảng trắng
    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


# =========================================================
# PARSE VOCAB BLOCK
# =========================================================

def parse_vocab_block(block):

    if len(block) < 3:
        return None

    # -----------------------------------------------------
    # STT
    # -----------------------------------------------------

    stt = block[0]

    # -----------------------------------------------------
    # HANZI
    # -----------------------------------------------------

    hanzi = block[1]

    if not is_hanzi(hanzi):
        return None

    # -----------------------------------------------------
    # TÌM TỪ LOẠI
    #
    # Ví dụ:
    #
    # 不
    # bù
    # Trạng từ
    #
    # hoặc:
    #
    # 老师
    # lǎo
    # shī
    # Danh từ
    # -----------------------------------------------------

    pos_index = None

    for i in range(
        2,
        len(block)
    ):

        if block[i] in POS_LIST:

            pos_index = i

            break

    if pos_index is None:
        return None

    # -----------------------------------------------------
    # PINYIN
    #
    # Tất cả những dòng giữa Hanzi và Từ loại
    #
    # 老师
    # lǎo
    # shī
    # Danh từ
    #
    # => lǎo shī
    # -----------------------------------------------------

    pinyin_parts = block[
        2:pos_index
    ]

    pinyin_parts = [
        x.strip()
        for x in pinyin_parts
        if x.strip()
    ]

    pinyin = " ".join(
        pinyin_parts
    )

    # -----------------------------------------------------
    # TỪ LOẠI
    # -----------------------------------------------------

    pos = block[
        pos_index
    ].strip()

    # -----------------------------------------------------
    # NGHĨA
    #
    # Lấy từ sau Từ loại
    # đến trước "Ví dụ"
    # -----------------------------------------------------

# -----------------------------------------------------
# NGHĨA
# -----------------------------------------------------

    meaning_parts = []

    meaning_number = None

    for line in block[pos_index + 1:]:

        line = line.strip()

        # ---------------------------------------------
        # Gặp Ví dụ => hết phần nghĩa
        # ---------------------------------------------

        if line == "Ví dụ":
            break

        # ---------------------------------------------
        # Bỏ dấu *
        # ---------------------------------------------

        if line == "*":
            continue

        # ---------------------------------------------
        # Số thứ tự nghĩa
        #
        # 1
        # .
        # nghĩa 1
        #
        # => 1. nghĩa 1
        # ---------------------------------------------

        if re.fullmatch(r"\d+", line):

            meaning_number = line

            continue

        # ---------------------------------------------
        # Dấu . đứng sau số
        # ---------------------------------------------

        if line in [".", "．"]:

            continue

        # ---------------------------------------------
        # Nếu đang có số nghĩa
        # ---------------------------------------------

        if meaning_number is not None:

            meaning_parts.append(
                f"{meaning_number}. {line}"
            )

            meaning_number = None

        else:

            meaning_parts.append(
                line
            )


    # -----------------------------------------------------
    # GHÉP NGHĨA
    # -----------------------------------------------------

    meaning = "; ".join(
        meaning_parts
    )

    meaning = re.sub(
        r"\s+",
        " ",
        meaning
    ).strip()

    # Không để ; dư ở cuối
    meaning = meaning.strip(
        " ;"
    )

    return {
        "Hanzi": hanzi,
        "Pinyin": pinyin,
        "Từ loại": pos,
        "Nghĩa": meaning
    }


# =========================================================
# SCRAPE VOCAB
# =========================================================

def scrape_vocab(url):

    soup = get_page(url)

    # -----------------------------------------------------
    # Lấy text
    # -----------------------------------------------------

    text = soup.get_text(
        "\n",
        strip=True
    )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    # -----------------------------------------------------
    # Tìm phần Từ vựng
    # -----------------------------------------------------

    start = None

    for i, line in enumerate(lines):

        if line == "Từ vựng":

            # Tìm STT đầu tiên: 01
            for j in range(
                i + 1,
                len(lines)
            ):

                if (
                    lines[j] == "01"
                    and j + 1 < len(lines)
                    and is_hanzi(lines[j + 1])
                ):

                    start = j
                    break

            if start is not None:
                break

    if start is None:

        raise Exception(
            "Không tìm thấy danh sách từ vựng."
        )

    # -----------------------------------------------------
    # Tìm tất cả vị trí bắt đầu của từ
    # -----------------------------------------------------

    vocab_positions = []

    for i in range(
        start,
        len(lines)
    ):

        if is_vocab_start(
            lines,
            i
        ):

            vocab_positions.append(i)

    # -----------------------------------------------------
    # Tạo block
    # -----------------------------------------------------

    blocks = []

    for index, position in enumerate(
        vocab_positions
    ):

        # Điểm kết thúc
        if index + 1 < len(
            vocab_positions
        ):

            end = vocab_positions[
                index + 1
            ]

        else:

            end = len(lines)

            # Không cần lấy quá phần vocabulary
            for j in range(
                position,
                len(lines)
            ):

                if lines[j] == "Ngữ pháp":

                    end = j
                    break

        block = lines[
            position:end
        ]

        blocks.append(
            block
        )

    # -----------------------------------------------------
    # Parse từng block
    # -----------------------------------------------------

    results = []

    for block in blocks:

        item = parse_vocab_block(
            block
        )

        if item:

            results.append(
                item
            )

    # -----------------------------------------------------
    # Chống duplicate trong lần cào
    # -----------------------------------------------------

    unique = []

    seen = set()

    for item in results:

        key = (
            item["Hanzi"].strip(),
            item["Pinyin"].strip()
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(item)

    return unique


# =========================================================
# LOAD EXISTING EXCEL
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


# =========================================================
# SAVE EXCEL
# =========================================================

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

    # -----------------------------------------------------
    # Gộp dữ liệu cũ và mới
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Đảm bảo đủ cột
    # -----------------------------------------------------

    for column in [
        "Hanzi",
        "Pinyin",
        "Từ loại",
        "Nghĩa"
    ]:

        if column not in combined.columns:

            combined[column] = ""

    # -----------------------------------------------------
    # Chuẩn hóa text
    # -----------------------------------------------------

    combined["Hanzi"] = (
        combined["Hanzi"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    combined["Pinyin"] = (
        combined["Pinyin"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    combined["Từ loại"] = (
        combined["Từ loại"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    combined["Nghĩa"] = (
        combined["Nghĩa"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # -----------------------------------------------------
    # Chống duplicate
    # -----------------------------------------------------

    combined = combined.drop_duplicates(
        subset=[
            "Hanzi",
            "Pinyin"
        ],
        keep="first"
    )

    # -----------------------------------------------------
    # STT
    # -----------------------------------------------------

    combined.insert(
        0,
        "STT",
        range(
            1,
            len(combined) + 1
        )
    )

    # -----------------------------------------------------
    # Đúng thứ tự cột
    # -----------------------------------------------------

    combined = combined[
        [
            "STT",
            "Hanzi",
            "Pinyin",
            "Từ loại",
            "Nghĩa"
        ]
    ]

    # -----------------------------------------------------
    # Ghi Excel
    # -----------------------------------------------------

    combined.to_excel(
        OUTPUT_FILE,
        index=False
    )

    return (
        len(new_df),
        len(combined)
    )
