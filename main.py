import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns


affirmative = ("Yea", "Aye")
negative = ("Nay", "No")
positional = affirmative + negative
non_vote = ("Not Voting", "Present")
regular = positional + non_vote


def fetch_states(conn):
    states = [state[0] for state in pd.read_sql_query(
        sql="""
            select name from states
        """,
        con=conn
    ).values]
    return states


def fetch_roll_vote(roll_id, conn):
    roll = pd.read_sql_query(
        sql="""
            select * from rolls
            where roll_id = ?
        """,
        con=conn,
        params=(roll_id,)
    )
    return roll


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


def votes_for_state(state, conn):
    votes = pd.read_sql_query(
        sql=f"""
            select
                vote,
                first_name || " " || last_name || " (" || party_designation || ")" as name
            from
                votes
            join
                reps on
                    reps.rep_id = votes.rep_id
            where
                state = ? and
                vote in {regular}
        """,
        con=conn,
        params=(state,)
    )
    return votes


def fetch_roll_vote_count(roll_id, conn):
    roll = fetch_roll_vote(roll_id, conn)
    counts = pd.read_sql_query(
        sql="""
            select * from rolls
            join votes on votes.roll_id = rolls.roll_id
            where rolls.roll_id = ?
        """,
        con=conn,
        params=(roll_id,)
    ).value_counts("vote").sort_values(ascending=False)
    counts = pd.DataFrame(counts).reset_index()
    counts.columns = ["vote", "count"]

    cols = counts["vote"].values.tolist()
    vals = [(x,) for x in counts["count"].values.tolist()]
    data = dict(zip(
        cols,
        vals
    ))
    counts = pd.DataFrame(data)
    roll_count = pd.concat(
        [roll, counts],
        axis=1
    )
    return roll_count


def fetch_all_rolls_with_votes(conn, last_roll_call, first_roll_call=1, year=2023):
    rolls_list = []
    roll_call_range = range(
        first_roll_call,
        last_roll_call+1
    )
    for roll_call in roll_call_range:
        roll_id = int(f"{year}{roll_call}")
        rolls_list.append(fetch_roll_vote_count(roll_id, conn))
    return pd.concat(rolls_list).reset_index().drop("index", axis=1)


def main():
    # if "ss" not in locals():
    #     ss = st.session_state
    try:
        ss
    except NameError:
        ss = st.session_state

    db_path = "congress_roll_calls.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # st.dataframe(fetch_roll_vote_count(2023192, conn))
    # st.dataframe(fetch_all_rolls_with_votes(conn, 21, 2))
    first_21_rolls = fetch_all_rolls_with_votes(conn, 21)
    first_21_rolls["roll_id"] = first_21_rolls["roll_id"].astype(str)
    st.dataframe(first_21_rolls)

    if "states" not in ss:
        ss.states = fetch_states(conn)

    st.header("US House Votes, 118th Congress")

    if "all_rolls" not in ss:
        ss.all_rolls = pd.read_sql_query(
            sql="""
                select * from rolls
            """,
            con=conn
        )
    if "latest_roll_call" not in ss:
        ss.latest_roll_call = int(
            ss.all_rolls["roll_call"].max()
        )
    if "latest_roll_id" not in ss:
        ss.latest_roll_id = int(
            f"2023{ss.latest_roll_call}"
        )
    if "all_rolls_with_votes" not in ss:
        ss.all_rolls_with_votes = fetch_all_rolls_with_votes(conn, ss.latest_roll_call)
    # st.dataframe(ss.all_rolls_with_votes, use_container_width=True)

    with st.expander(
        "All votes cast against the rep's own party",
        expanded=True
    ):
        if "all_dissenters" not in ss:
            ss.all_dissenters = fetch_all_dissenters(conn, cur, False)
            ss.all_dissenters["roll_id"] = ss.all_dissenters["roll_id"].astype(str)
        st.dataframe(ss.all_dissenters, use_container_width=True)

    with st.expander(
        "Select a state and district to see that rep's dissenting votes",
        expanded=True
    ):
        col_state, col_district = st.columns(2)
        with col_state:
            state = st.selectbox(
                "Select State",
                options=ss.states
            )
        with col_district:
            district = st.selectbox(
                "Select District",
                options=ss.all_dissenters[
                    ss.all_dissenters["state"] == state
                ]["district"]
            )

        st.dataframe(
            ss.all_dissenters[
                (ss.all_dissenters["state"] == state) &
                (ss.all_dissenters["district"] == district)
            ],
            use_container_width=True
        )

    with st.expander(
        "Number of votes cast by each rep in the selected state",
        expanded=True
    ):
        # Show votes for reps by state
        state = st.selectbox(
            "Select a state",
            options=ss.states
        )
        state_vote = votes_for_state(state, conn)
        state_vote_pivot = state_vote.pivot_table(
            index="name",
            columns="vote",
            aggfunc=len,
            fill_value=0
        )

        fig, ax = plt.subplots(figsize=(12, 12))
        sns.heatmap(
            state_vote_pivot,
            annot=True,
            cmap="Greens"
        )
        plt.title(f"Votes for State of {state}")
        plt.xticks(
            rotation=45,
            ha="right"
        )
        party_colors = {
            "D": "blue",
            "R": "red",
            "L": "yellow"
        }
        for label in ax.get_yticklabels():
            party_designation = label.get_text()[-2]
            label.set_color(party_colors[party_designation])
        st.pyplot(fig)

    # with st.expander(
    #     "Votes by vote type",
    #     expanded=True
    # ):
        # vote_questions = all_rolls_with_votes["vote_question"].unique()
        # vote_question = st.selectbox(
        #     "Select a Vote Question",
        #     options=vote_questions,
        #     index=7  # "On Passage"
        # )
        #
        # st.dataframe(
        #     all_rolls_with_votes[
        #         all_rolls_with_votes["vote_question"] == vote_question
        #     ]
        # )


if __name__ == "__main__":
    main()
