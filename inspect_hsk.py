import re

with open("hsk.html", "r", encoding="utf-8") as f:
    html = f.read()

keywords = [
    "navigation",
    "nav",
    "sidebar",
    "Xin chào",
    "hsk1-bai-1-xin-chao",
    "hsk1-bai-139-thoi-gian",
]

for keyword in keywords:

    print("\n")
    print("=" * 100)
    print("KEYWORD:", keyword)
    print("=" * 100)

    matches = list(
        re.finditer(
            re.escape(keyword),
            html,
            re.IGNORECASE
        )
    )

    print(
        "Số lần xuất hiện:",
        len(matches)
    )

    for match in matches[:3]:

        start = max(
            0,
            match.start() - 2000
        )

        end = min(
            len(html),
            match.end() + 4000
        )

        print(
            html[start:end]
        )

        print(
            "\n" + "-" * 100
        )