import streamlit as st
import pandas as pd
import sqlite3


def main():
    db_path = "congress_roll_calls.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    st.header("Main Title")


if __name__ == "__main__":
    main()
