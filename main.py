import streamlit as st
import pandas as pd
import sqlite3


def dissenting_votes(roll_id, conn, include_non_votes=True):
    present = "" if include_non_votes else "Present"
    not_voting = "" if include_non_votes else "Not Voting"
    non_votes = (present, not_voting)

    dissenters = pd.read_sql_query(
        sql=f"""
            with party_votes as (
                select
                    vote,
                    party,
                    count(party) as vote_count
                from
                    votes
                join
                    reps on
                        reps.rep_id = votes.rep_id
                where
                    roll_id = {roll_id}
                group by
                    party,
                    vote
                order by
                    vote_count desc
            ), majority_votes as(
                select
                    party,
                    vote as party_vote
                from
                    party_votes
                group by
                    party
            )
            select
                votes.roll_id,
                reps.party,
                vote,
                first_name || " " || last_name as name,
                state,
                district,
                phone
            from
                votes
            join
                reps on
                    reps.rep_id = votes.rep_id
            join
                majority_votes on
                    majority_votes.party = reps.party
            where
                roll_id = {roll_id} and
                vote <> party_vote and
                vote <> ? and
                vote <> ?
            order by
                reps.party,
                vote,
                last_name,
                first_name
        """,
        con=conn,
        params=non_votes
    )
    return dissenters


def fetch_all_dissenters(conn, cur, include_non_votes=False):
    latest_roll_call = cur.execute("""
        select roll_call from rolls
        order by roll_call desc
    """).fetchone()[0]

    all_votes = []
    for roll in range(latest_roll_call):
        roll_id_num = int(
            f"2023{roll+1}"
        )
        vote = dissenting_votes(roll_id_num, conn, include_non_votes)
        all_votes.append(vote)
    all_dissenters = pd.concat(all_votes).reset_index().drop("index", axis=1)
    return all_dissenters


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
    # st.dataframe(all_rolls)

    roll_id = st.slider(
        "Roll Call",
        min_value=int(all_rolls.roll_call.min()),
        max_value=int(all_rolls.roll_call.max()),
        value=int(all_rolls.roll_call.min()),
        step=1
    )
    dissenters = dissenting_votes(int(f"2023{roll_id}"), conn, False)
    st.dataframe(dissenters, use_container_width=True)

    all_dissenters = fetch_all_dissenters(conn, cur, False)
    st.dataframe(all_dissenters)


if __name__ == "__main__":
    main()
