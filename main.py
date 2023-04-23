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


def roll_vote_count(roll_id, conn):
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
    counts=pd.DataFrame(counts).reset_index()
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


def fetch_all_rolls_with_votes(conn, latest_roll_call):
    rolls_list = []
    for roll_call in range(1, latest_roll_call + 1):
        rolls_list.append(roll_vote_count(roll_call, conn))
    return pd.concat(rolls_list, axis=1)


def main():
    db_path = "congress_roll_calls.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    states = fetch_states(conn)

    st.header("Main Title")

    all_rolls = pd.read_sql_query(
        sql="""
            select * from rolls
        """,
        con=conn
    )
    latest_roll_call = int(
        all_rolls["roll_id"].max()
    )
    print(f"{latest_roll_call = }")
    # all_rolls_with_votes = fetch_all_rolls_with_votes(conn, latest_roll_call)
    # st.dataframe(all_rolls_with_votes)

    all_dissenters = fetch_all_dissenters(conn, cur, False)
    st.dataframe(all_dissenters, use_container_width=True)

    col_state, col_district = st.columns(2)
    with col_state:
        state = st.selectbox(
            "Select State",
            options=states
        )
    with col_district:
        district = st.selectbox(
            "Select District",
            options=all_dissenters[
                all_dissenters["state"] == state
            ]["district"]
        )

    st.dataframe(
        all_dissenters[
            (all_dissenters["state"] == state) &
            (all_dissenters["district"] == district)
        ],
        use_container_width=True
    )

    # Show votes for reps by state
    state = st.selectbox(
        "Select a state",
        options=states
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


if __name__ == "__main__":
    main()
