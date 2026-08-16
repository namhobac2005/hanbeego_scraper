import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

from scraper import scrape_vocab


BASE_URL = "https://hanbeego.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}


# =========================================================
# HTTP
# =========================================================

def get_html(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text


# =========================================================
# PARSE NAVIGATION
# =========================================================

def extract_navigation(html, hsk_level):
    """
    Extract HSK navigation từ Next.js RSC payload.

    Không hard-code topic hoặc lesson.
    Lấy trực tiếp units -> lessons -> href
    theo order của website.
    """

    # =====================================================
    # 1. Tìm tất cả Next.js RSC payload
    # =====================================================

    pattern = re.compile(
        r'self\.__next_f\.push\(\[1,"(.*?)"\]\)',
        re.DOTALL
    )

    payloads = pattern.findall(html)

    if not payloads:
        raise Exception(
            "Không tìm thấy Next.js RSC payload."
        )

    # =====================================================
    # 2. Decode JavaScript string
    # =====================================================

    decoded_parts = []

    for payload in payloads:

        try:
            # Payload đang chứa escape kiểu:
            #
            # \"units\"
            # \u0026
            # \/
            #
            decoded = (
                payload
                .replace('\\"', '"')
                .replace("\\/", "/")
            )

            decoded = re.sub(
                r"\\u([0-9a-fA-F]{4})",
                lambda m: chr(
                    int(m.group(1), 16)
                ),
                decoded
            )

            decoded_parts.append(
                decoded
            )

        except Exception:
            # Nếu unicode_escape gây lỗi
            # thì giữ nguyên payload
            decoded_parts.append(
                payload
            )

    decoded_html = "\n".join(
        decoded_parts
    )

    # =====================================================
    # 3. Tìm "units":[ ... ]
    # =====================================================

    marker = '"units":'

    position = decoded_html.find(
        marker
    )

    if position == -1:

        raise Exception(
            "Next.js payload có tồn tại "
            "nhưng không tìm thấy 'units'."
        )

    json_start = (
        position
        + len(marker)
    )

    # =====================================================
    # 4. Parse JSON array
    # =====================================================

    decoder = json.JSONDecoder()

    try:

        units, consumed = decoder.raw_decode(
            decoded_html[json_start:]
        )

    except json.JSONDecodeError as e:

        # In một đoạn để debug
        preview_start = max(
            0,
            json_start - 200
        )

        preview_end = min(
            len(decoded_html),
            json_start + 1000
        )

        preview = decoded_html[
            preview_start:preview_end
        ]

        raise Exception(
            "Không parse được units.\n\n"
            f"Vị trí lỗi: {e.pos}\n\n"
            f"Dữ liệu gần đó:\n{preview}"
        )

    # =====================================================
    # 5. Validate
    # =====================================================

    if not isinstance(
        units,
        list
    ):

        raise Exception(
            "'units' không phải danh sách."
        )

    if not units:

        raise Exception(
            "'units' tồn tại nhưng rỗng."
        )

    # =====================================================
    # 6. Build navigation
    # =====================================================

    navigation = []

    for unit in units:

        if not isinstance(
            unit,
            dict
        ):
            continue

        topic_title = str(
            unit.get(
                "title",
                ""
            )
        ).strip()

        topic_order = unit.get(
            "order",
            len(navigation) + 1
        )

        lessons_raw = unit.get(
            "lessons",
            []
        )

        lessons = []

        for lesson in lessons_raw:

            if not isinstance(
                lesson,
                dict
            ):
                continue

            href = lesson.get(
                "href"
            )

            if not href:
                continue

            # =================================================
            # Chỉ nhận lesson thuộc HSK hiện tại
            # =================================================

            parsed = urlparse(
                href
            )

            path = parsed.path.rstrip("/")

            prefix = (
                f"/hsk/{hsk_level}/"
            )

            if not path.startswith(
                prefix
            ):
                continue

            # =================================================
            # Loại URL phụ
            # =================================================

            blocked = (
                "/play",
                "/quiz",
                "/flashcard",
                "/learn",
                "/practice",
                "/grammar",
                "/vocab",
                "/writing",
            )

            if any(
                block in path
                for block in blocked
            ):
                continue

            url = urljoin(
                BASE_URL,
                href
            )

            lessons.append({

                "order": lesson.get(
                    "order",
                    len(lessons) + 1
                ),

                "title": str(
                    lesson.get(
                        "title",
                        ""
                    )
                ).strip(),

                "slug": lesson.get(
                    "slug",
                    ""
                ),

                "url": url,

                "vocabCount": lesson.get(
                    "vocabCount",
                    0
                ),

                "grammarCount": lesson.get(
                    "grammarCount",
                    0
                ),

                "dialogueCount": lesson.get(
                    "dialogueCount",
                    0
                ),

                "minutes": lesson.get(
                    "minutes",
                    0
                ),

                "status": lesson.get(
                    "status",
                    ""
                )

            })

        # =====================================================
        # Giữ thứ tự lesson của website
        # =====================================================

        lessons.sort(
            key=lambda x: x["order"]
        )

        if lessons:

            navigation.append({

                "order": topic_order,

                "title": topic_title,

                "total": len(lessons),

                "lessons": lessons

            })

    # =====================================================
    # Giữ thứ tự topic
    # =====================================================

    navigation.sort(
        key=lambda x: x["order"]
    )

    if not navigation:

        raise Exception(
            f"Không tìm thấy lesson HSK {hsk_level}."
        )

    return navigation


# =========================================================
# DISCOVER LESSONS
# =========================================================

def discover_lessons(hsk_level):

    hsk_url = (
        f"{BASE_URL}/hsk"
    )

    html = get_html(
        hsk_url
    )


    navigation = extract_navigation(
        html,
        hsk_level
    )


    lessons = []


    for topic in navigation:

        for lesson in topic["lessons"]:

            lessons.append({

                "topic": topic["title"],

                "topic_order": topic["order"],

                "title": lesson["title"],

                "lesson_order": lesson["order"],

                "url": lesson["url"],

                "slug": lesson["slug"],

                "vocabCount": lesson["vocabCount"],

            })


    return navigation, lessons


# =========================================================
# CRAWL ALL HSK
# =========================================================

def scrape_all_hsk(
    hsk_level=1,
    delay=0.3,
    progress_callback=None
):

    navigation, lesson_list = discover_lessons(
        hsk_level
    )


    if not lesson_list:

        raise Exception(
            f"Không tìm thấy lesson HSK {hsk_level}."
        )


    # =====================================================
    # IN NAVIGATION
    # =====================================================

    print()
    print("=" * 70)
    print(
        f"📚 HSK {hsk_level}"
    )
    print("=" * 70)


    for topic in navigation:

        print()
        print(
            f"📂 {topic['title']}: "
            f"{len(topic['lessons'])} bài"
        )


        for lesson in topic["lessons"]:

            print(
                f"   - "
                f"{lesson['order']} "
                f"{lesson['title']}"
            )


    print()
    print(
        f"📖 Tổng cộng: "
        f"{len(lesson_list)} bài"
    )

    print()


    # =====================================================
    # CRAWL
    # =====================================================

    all_vocab = []

    lesson_results = []

    total = len(
        lesson_list
    )


    for index, lesson in enumerate(
        lesson_list,
        start=1
    ):

        topic = lesson["topic"]

        title = lesson["title"]

        lesson_url = lesson["url"]


        try:

            vocab = scrape_vocab(
                lesson_url
            )


            all_vocab.extend(
                vocab
            )


            result = {

                "topic": topic,

                "title": title,

                "url": lesson_url,

                "count": len(vocab),

                "status": "OK",

                "error": ""

            }


            lesson_results.append(
                result
            )


            # -------------------------------------------------
            # CALLBACK
            # -------------------------------------------------

            if progress_callback:

                progress_callback(

                    index,

                    total,

                    topic,

                    title,

                    lesson_url,

                    len(vocab),

                    "OK",

                    ""

                )


            # -------------------------------------------------
            # CLI
            # -------------------------------------------------

            print(

                f"[{index}/{total}] "
                f"✓ {topic} / "
                f"{title} — "
                f"{len(vocab)} từ"

            )


        except Exception as e:

            error = str(e)


            result = {

                "topic": topic,

                "title": title,

                "url": lesson_url,

                "count": 0,

                "status": "ERROR",

                "error": error

            }


            lesson_results.append(
                result
            )


            if progress_callback:

                progress_callback(

                    index,

                    total,

                    topic,

                    title,

                    lesson_url,

                    0,

                    "ERROR",

                    error

                )


            print(

                f"[{index}/{total}] "
                f"✗ {topic} / "
                f"{title} — "
                f"LỖI: {error}"

            )


        if delay > 0:

            time.sleep(
                delay
            )


    # =====================================================
    # DEDUPLICATE
    # =====================================================

    unique = []

    seen = set()


    for item in all_vocab:

        hanzi = str(
            item.get(
                "Hanzi",
                ""
            )
        ).strip()


        pinyin = str(
            item.get(
                "Pinyin",
                ""
            )
        ).strip()


        key = (

            hanzi,

            pinyin.casefold()

        )


        if not hanzi:

            continue


        if key in seen:

            continue


        seen.add(
            key
        )


        unique.append({

            "Hanzi": hanzi,

            "Pinyin": pinyin,

            "Từ loại": item.get(
                "Từ loại",
                ""
            ),

            "Nghĩa": item.get(
                "Nghĩa",
                ""
            )

        })


    return (
        unique,
        lesson_results,
        navigation
    )


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    print("=" * 70)
    print("🐝 HANBEEGO DYNAMIC HSK CRAWLER")
    print("=" * 70)


    try:

        level = int(
            input(
                "Nhập HSK muốn cào (1-9): "
            ).strip()
        )


        # -------------------------------------------------
        # DISCOVER
        # -------------------------------------------------

        navigation, lessons = discover_lessons(
            level
        )


        print()
        print(
            f"🔎 HSK {level}"
        )

        print(
            f"📂 Chủ đề: "
            f"{len(navigation)}"
        )

        print(
            f"📖 Bài học: "
            f"{len(lessons)}"
        )


        print()


        for topic in navigation:

            print(
                f"📂 {topic['title']}: "
                f"{len(topic['lessons'])} bài"
            )


            for lesson in topic["lessons"]:

                print(

                    f"   - "
                    f"{lesson['order']} "
                    f"{lesson['title']} "
                    f"→ {lesson['url']}"

                )


        print()

        input(
            "Nhấn ENTER để bắt đầu crawl..."
        )


        # -------------------------------------------------
        # CRAWL
        # -------------------------------------------------

        data, lesson_results, navigation = (
            scrape_all_hsk(
                hsk_level=level
            )
        )


        print()
        print("=" * 70)
        print("🎉 HOÀN TẤT")
        print("=" * 70)


        success = sum(
            1
            for x in lesson_results
            if x["status"] == "OK"
        )


        failed = sum(
            1
            for x in lesson_results
            if x["status"] != "OK"
        )


        print(
            f"Lesson thành công: "
            f"{success}/{len(lesson_results)}"
        )


        print(
            f"Lesson lỗi: "
            f"{failed}"
        )


        print(
            f"Từ duy nhất: "
            f"{len(data)}"
        )


    except Exception as e:

        print()
        print(
            f"❌ LỖI: {e}"
        )