import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from scraper import scrape_vocab


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
