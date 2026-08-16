import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from scraper import scrape_vocab
from crawler import scrape_all_hsk

st.set_page_config(
    page_title="HanBeeGo Vocabulary Scraper",
    page_icon="🐝"
)

st.title("🐝 HanBeeGo Vocabulary Scraper")

url = st.text_input(
    "Dán URL HanBeeGo:",
    placeholder="https://hanbeego.com/hsk/1/..."
)

if st.button("🚀 Cào dữ liệu"):

    if not url:
        st.warning("Vui lòng nhập URL.")

    else:

        try:

            with st.spinner("Đang cào dữ liệu..."):

                data = scrape_vocab(url)

            st.success(
                f"Tìm thấy {len(data)} từ vựng."
            )

            df = pd.DataFrame(data)

            st.dataframe(
                df,
                use_container_width=True
            )
            copy_df = df.copy()

            copy_text = copy_df.to_csv(
                sep="\t",
                index=False,
                header=False
            )
            components.html(
                f"""
                <button onclick="copyText()">
                    Copy nội dung
                </button>

                <script>
                function copyText() {{

                    const text = `{copy_text}`;

                    navigator.clipboard.writeText(text);

                    alert("Đã copy!");
                }}
                </script>
                """,
                height=60
            )

        except Exception as e:

            st.error(
                f"Lỗi: {e}"
            )
st.divider()

st.subheader("📚 Cào toàn bộ HSK")

hsk_level = st.selectbox(
    "Chọn cấp độ HSK:",
    [1, 2, 3, 4, 5, 6],
    key="hsk_level"
)


if st.button(
    "🚀 Cào toàn bộ HSK",
    key="crawl_all_hsk"
):

    progress = st.progress(0)

    status = st.empty()

    progress_container = st.container()

    crawl_logs = []


    try:

        # =================================================
        # CALLBACK
        # =================================================

        def update_progress(
            current,
            total,
            topic,
            title,
            url,
            count,
            crawl_status,
            error
        ):

            percent = int(
                current / total * 100
            )

            progress.progress(
                percent
            )


            # =================================================
            # TRẠNG THÁI HIỆN TẠI
            # =================================================

            if crawl_status == "OK":

                status.markdown(
                    f"""
                    **Đang cào:** {current}/{total}  

                    📂 **{topic}**  

                    📖 **{title}**  

                    📚 Tìm thấy **{count} từ**
                    """
                )

            else:

                status.error(
                    f"""
                    ❌ **{current}/{total} — {title}**

                    📂 Chủ đề: {topic}

                    🔗 {url}

                    ❌ Lỗi: {error}
                    """
                )


            # =================================================
            # LƯU LOG
            # =================================================

            crawl_logs.append({

                "stt": current,

                "topic": topic,

                "title": title,

                "url": url,

                "count": count,

                "status": crawl_status,

                "error": error

            })


            # =================================================
            # HIỂN THỊ TIẾN TRÌNH
            # =================================================

            with progress_container:

                st.markdown(
                    f"### 📋 Tiến trình "
                    f"({current}/{total})"
                )


                for log in crawl_logs:

                    if log["status"] == "OK":

                        st.write(
                            f"✅ **{log['stt']}. "
                            f"{log['title']}** "
                            f"— {log['count']} từ"
                        )

                    else:

                        st.write(
                            f"❌ **{log['stt']}. "
                            f"{log['title']}** "
                            f"— LỖI"
                        )


                    st.caption(
                        f"📂 {log['topic']}  |  "
                        f"🔗 {log['url']}"
                    )


        # =================================================
        # CRAWL
        # =================================================

        with st.spinner(
            f"Đang tìm navigation và cào "
            f"toàn bộ HSK {hsk_level}..."
        ):

            data, lessons, topics = scrape_all_hsk(

                hsk_level=hsk_level,

                progress_callback=update_progress

            )


        progress.progress(100)


        # =================================================
        # THỐNG KÊ
        # =================================================

        success_count = sum(

            1

            for lesson in lessons

            if lesson["status"] == "OK"

        )


        failed_lessons = [

            lesson

            for lesson in lessons

            if lesson["status"] != "OK"

        ]


        error_count = len(
            failed_lessons
        )


        st.success(

            f"🎉 Hoàn tất! "

            f"{success_count}/{len(lessons)} bài — "

            f"{len(data)} từ duy nhất."

        )


        # =================================================
        # TỔNG QUAN THEO CHỦ ĐỀ
        # =================================================

        st.markdown(
            "### 📚 Tổng quan theo chủ đề"
        )


        for topic in topics:

            topic_title = topic["title"]


            topic_lessons = [

                lesson

                for lesson in lessons

                if lesson["topic"] == topic_title

            ]


            topic_success = sum(

                1

                for lesson in topic_lessons

                if lesson["status"] == "OK"

            )


            topic_words = sum(

                lesson["count"]

                for lesson in topic_lessons

            )


            with st.expander(

                f"📂 {topic_title} "
                f"— {topic_success}/"
                f"{len(topic_lessons)} bài "
                f"— {topic_words} từ"

            ):

                for lesson in topic_lessons:

                    if lesson["status"] == "OK":

                        st.write(

                            f"✅ **{lesson['title']}** "
                            f"— {lesson['count']} từ"

                        )

                    else:

                        st.error(

                            f"❌ **{lesson['title']}** "
                            f"— {lesson['error']}"

                        )


                    st.caption(
                        lesson["url"]
                    )


        # =================================================
        # BÀI BỊ LỖI
        # =================================================

        if failed_lessons:

            st.warning(

                f"⚠️ Có "
                f"{error_count} bài không cào được."

            )


            with st.expander(
                "🔴 Xem chi tiết các bài lỗi"
            ):

                for lesson in failed_lessons:

                    st.error(

                        f"""
                        **{lesson['title']}**

                        📂 Chủ đề: {lesson['topic']}

                        🔗 {lesson['url']}

                        ❌ Lỗi: {lesson['error']}
                        """

                    )

        else:

            st.success(
                "✅ Tất cả bài đều cào thành công!"
            )


        # =================================================
        # DATAFRAME
        # =================================================

        st.markdown(
            "### 📊 Dữ liệu từ vựng"
        )


        df_all = pd.DataFrame(
            data
        )


        st.dataframe(

            df_all,

            use_container_width=True,

            hide_index=True

        )


        # =================================================
        # COPY GOOGLE SHEETS
        # =================================================

        copy_text = df_all.to_csv(

            sep="\t",

            index=False,

            header=False

        )


        components.html(

            f"""
            <button
                onclick="copyText()"
                style="
                    padding: 8px 16px;
                    border-radius: 6px;
                    border: 1px solid #ccc;
                    cursor: pointer;
                    font-size: 14px;
                "
            >
                📋 Copy Google Sheets
            </button>

            <script>
            function copyText() {{

                const text = `{copy_text}`;

                navigator.clipboard.writeText(text);

                alert("Đã copy dữ liệu!");

            }}
            </script>
            """,

            height=55

        )


        # =================================================
        # CSV
        # =================================================

        excel_df = df_all.copy()


        excel_df.insert(

            0,

            "STT",

            range(
                1,
                len(excel_df) + 1
            )

        )


        excel_data = excel_df.to_csv(

            index=False

        ).encode(
            "utf-8-sig"
        )


        st.download_button(

            "📥 Tải CSV",

            data=excel_data,

            file_name=(
                f"hanbeego_hsk{hsk_level}.csv"
            ),

            mime="text/csv",

            key="download_hsk"

        )


    except Exception as e:

        st.error(
            f"❌ Lỗi: {e}"
        )