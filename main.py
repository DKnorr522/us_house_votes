import streamlit as st
import pandas as pd
import sqlite3


def main():
    db_path = "congress_roll_calls.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    st.header("Main Title")

    all_rolls = pd.read_sql_query(
        sql="""
            select * from rolls
        """,
        con=conn
    )
    st.dataframe(all_rolls)


if __name__ == "__main__":
    main()
