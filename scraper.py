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
# CHECK HANZI
# =========================================================

# Hỗ trợ toàn bộ chuỗi Hanzi, không giới hạn 1/2 ký tự.
# Bao gồm CJK Unified Ideographs và Extension A.
HANZI_RE = re.compile(r"^[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]+$")


def is_hanzi(text):
    if not text:
        return False

    text = text.strip()

    return bool(HANZI_RE.fullmatch(text))


# =========================================================
# CHECK VOCAB START
# =========================================================

# HanBeeGo đánh số từ 01, 02,... nhưng không nên phụ thuộc
# cứng vào đúng 2 chữ số. Hỗ trợ 1-3 chữ số để dùng được
# cho mọi bài/HSK và không làm mất các từ có Hanzi dài.
VOCAB_NUMBER_RE = re.compile(r"^\d{1,3}$")


def find_pos_index(lines, start_index, max_scan=12):
    """
    Tìm vị trí từ loại ngay sau Hanzi + Pinyin.

    Không giả định Pinyin có bao nhiêu âm tiết:
        bù
        lǎo
        shī
        lǎo shī
        zài jiàn
        xué sheng
    đều được hỗ trợ.
    """

    end = min(
        len(lines),
        start_index + max_scan
    )

    for i in range(start_index, end):
        if lines[i].strip() in POS_LIST:
            return i

    return None


def is_vocab_start(lines, index):
    """
    Một entry vocabulary hợp lệ phải có:

        STT
        Hanzi
        Pinyin (1 hoặc nhiều dòng)
        Từ loại

    Nhờ kiểm tra cả Từ loại, các số 01/02 xuất hiện
    trong nội dung khác sẽ không bị nhận nhầm thành từ mới.
    """

    if index >= len(lines):
        return False

    if not VOCAB_NUMBER_RE.fullmatch(
        lines[index].strip()
    ):
        return False

    if index + 1 >= len(lines):
        return False

    if not is_hanzi(lines[index + 1]):
        return False

    pos_index = find_pos_index(
        lines,
        index + 2
    )

    return pos_index is not None


# =========================================================
# CLEAN TEXT
# =========================================================

def clean_text(text):
    if text is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(text)
    ).strip()


# =========================================================
# CLEAN MEANING
# =========================================================

def clean_meaning(parts):
    """
    Giữ nguyên cấu trúc nhiều nghĩa:

        1
        .
        nghĩa A
        2
        .
        nghĩa B
        ghi chú B

    => 1. nghĩa A; 2. nghĩa B ghi chú B

    Nếu không có đánh số:
        nghĩa chính
        mô tả

    => nghĩa chính mô tả
    """

    if not parts:
        return ""

    groups = []
    current = []
    current_number = None

    for raw in parts:

        line = clean_text(raw)

        if not line:
            continue

        if line == "*":
            continue

        # Bỏ dấu chấm đứng riêng sau số nghĩa.
        if line in [".", "．"]:
            continue

        # Một số nguồn có "1", "2",...
        # đứng riêng để đánh số các nghĩa.
        if re.fullmatch(r"\d+", line):

            if current:
                text = " ".join(current).strip()

                if current_number is not None:
                    text = f"{current_number}. {text}"

                groups.append(text)

            current = []
            current_number = line

            continue

        current.append(line)

    # Lưu nhóm cuối.
    if current:

        text = " ".join(current).strip()

        if current_number is not None:
            text = f"{current_number}. {text}"

        groups.append(text)

    return "; ".join(
        group for group in groups if group
    )


# =========================================================
# PARSE VOCAB BLOCK
# =========================================================

def parse_vocab_block(block):

    if len(block) < 4:
        return None

    # -----------------------------------------------------
    # STT
    # -----------------------------------------------------

    stt = block[0].strip()

    if not VOCAB_NUMBER_RE.fullmatch(stt):
        return None

    # -----------------------------------------------------
    # HANZI
    # -----------------------------------------------------

    hanzi = block[1].strip()

    if not is_hanzi(hanzi):
        return None

    # -----------------------------------------------------
    # TÌM TỪ LOẠI
    # -----------------------------------------------------

    pos_index = find_pos_index(
        block,
        2
    )

    if pos_index is None:
        return None

    # -----------------------------------------------------
    # PINYIN
    #
    # Lấy toàn bộ nội dung giữa Hanzi và Từ loại.
    # Không giới hạn số âm tiết.
    #
    # Ví dụ:
    #   bù
    #   lǎo shī
    #   zài jiàn
    #   xué sheng
    # -----------------------------------------------------

    pinyin_parts = [
        clean_text(x)
        for x in block[2:pos_index]
        if clean_text(x)
    ]

    pinyin = " ".join(pinyin_parts)

    # -----------------------------------------------------
    # TỪ LOẠI
    # -----------------------------------------------------

    pos = clean_text(
        block[pos_index]
    )

    # -----------------------------------------------------
    # NGHĨA
    # -----------------------------------------------------

    meaning_lines = []

    for line in block[pos_index + 1:]:

        line = line.strip()

        if line == "Ví dụ":
            break

        meaning_lines.append(line)

    meaning = clean_meaning(
        meaning_lines
    )

    return {
        "Hanzi": hanzi,
        "Pinyin": pinyin,
        "Từ loại": pos,
        "Nghĩa": meaning
    }


# =========================================================
# FIND VOCABULARY SECTION
# =========================================================

def find_vocab_start(lines):
    """
    Tìm entry vocabulary đầu tiên sau tiêu đề 'Từ vựng'.

    Không phụ thuộc bài có bao nhiêu từ.
    """

    vocab_headers = {
        "Từ vựng",
        "Vocabulary"
    }

    for i, line in enumerate(lines):

        if line not in vocab_headers:
            continue

        # Tìm candidate đầu tiên có cấu trúc đầy đủ.
        for j in range(i + 1, len(lines)):

            if is_vocab_start(lines, j):
                return j

            # Nếu đã sang phần khác thì dừng.
            if lines[j] in {
                "Ngữ pháp",
                "Grammar",
                "Hội thoại",
                "Dialogues",
                "Bài tập"
            }:
                break

    return None


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
        clean_text(line)
        for line in text.splitlines()
        if clean_text(line)
    ]

    # -----------------------------------------------------
    # Tìm phần Từ vựng
    # -----------------------------------------------------

    start = find_vocab_start(lines)

    if start is None:
        raise Exception(
            "Không tìm thấy danh sách từ vựng."
        )

    # -----------------------------------------------------
    # Tìm tất cả entry vocabulary
    # -----------------------------------------------------

    vocab_positions = []

    for i in range(start, len(lines)):

        if is_vocab_start(lines, i):
            vocab_positions.append(i)

    if not vocab_positions:
        raise Exception(
            "Không tìm thấy từ vựng hợp lệ."
        )

    # -----------------------------------------------------
    # Tạo block
    # -----------------------------------------------------

    blocks = []

    for index, position in enumerate(vocab_positions):

        if index + 1 < len(vocab_positions):

            end = vocab_positions[index + 1]

        else:

            end = len(lines)

            # Dừng trước phần tiếp theo.
            section_headers = {
                "Ngữ pháp",
                "Grammar",
                "Hội thoại",
                "Dialogues",
                "Bài tập",
                "Exercises"
            }

            for j in range(position, len(lines)):

                if lines[j] in section_headers:
                    end = j
                    break

        block = lines[position:end]

        blocks.append(block)

    # -----------------------------------------------------
    # Parse từng block
    # -----------------------------------------------------

    results = []

    for block in blocks:

        item = parse_vocab_block(block)

        if item:
            results.append(item)

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