import streamlit as st
import numpy as np
import os
from py2neo import Graph
from pyvis.network import Network
import pandas as pd


def unique(list1):
    x = np.array(list1)
    return np.unique(x)


net = Network()


st.header("This is the Facebook Knowledge Graph")

st.markdown(
    """  -  Some Facebook data resides in a Neo4J database as nodes and relationships.
- __FB_account__ nodes are accounts with a facebookID (the URL), first_name, second_name and third_name derived from the account.
- The 'name' property is the name portion of the url.
- louvain_community is a calculated value,  as is the page_rank, betweenness and source_embeddingVectorFastRP."""
)

graph = Graph(
    os.environ.get("NEO4J_URL"),
    user="neo4j",  # os.environ.get("NEO4J_USR"),
    password=os.environ.get("NEO4J_PWD"),
)

neo4j_query = """
MATCH (fb:FB_account)
RETURN fb.facebookID AS url,
fb.name AS fb_name,
fb.first_name AS first_name,
fb.second_name AS second_name,
COALESCE(fb.first_name ,"") + ' ' + COALESCE(fb.second_name ,"") AS name
"""

fb_accounts = graph.run(neo4j_query).to_data_frame()
fb_urls = fb_accounts.url.unique()
fb_names = fb_accounts.fb_name.unique()
names = fb_accounts.name.unique()
first_names = fb_accounts.first_name.fillna("nan").unique()
second_names = fb_accounts.second_name.fillna("nan").unique()
all_names = np.hstack([first_names, second_names])
# all_names = first_names.extend(second_names)
# np.unique(all_names)
all_names = unique(all_names)
# unique(list1)

sb = st.sidebar

chosen_name_list = sb.multiselect(
    "Choose a name ... ",
    all_names,
    default=None,
    key="chosen_name_list",
)

if chosen_name_list:
    st.markdown(f"""  You have chosen {st.session_state.chosen_name_list} """)
    parameters = {"chosen_name_list": st.session_state.chosen_name_list}
    neo4j_query = f"""MATCH (fb:FB_account)
    WHERE
    SIZE(apoc.coll.intersection([fb.first_name, fb.second_name],  $chosen_name_list)) > 0
    WITH fb as fb
    OPTIONAL MATCH p = (fb)-[r1:HAS_TARGET]->()
    WITH fb as fb, COUNT(r1) AS times_as_source
    OPTIONAL MATCH (fb)-[r2:HAS_SOURCE]->()
    WITH fb as fb, times_as_source, COUNT(r2) AS times_as_target
    RETURN DISTINCT fb.facebookID AS facebook_url,
    fb.first_name AS first_name,
    fb.second_name AS second_name,
    fb.louvain_community AS community,
    fb.betweenness AS betweenness,
    fb.pagerank AS pagerank,
    times_as_source,
    times_as_target;"""
    # st.markdown(neo4j_query)
    chosen_account_metrics = graph.run(neo4j_query, parameters).to_data_frame()
    st.dataframe(chosen_account_metrics)

    neo4j_query = """MATCH (fb1:FB_account ),
          (fb2:FB_account )
          WHERE ID(fb1)<ID(fb2)
          AND SIZE(apoc.coll.intersection([fb1.first_name, fb1.second_name],  $chosen_name_list)) > 0
          AND SIZE(apoc.coll.intersection([fb2.first_name, fb2.second_name],  $chosen_name_list)) > 0
          WITH shortestPath((fb1)-[:HAS_SOURCE|HAS_TARGET*]-(fb2)) as p, fb1 AS fb1, fb2 AS fb2
          RETURN fb1.facebookID AS fb1, fb2.facebookID AS fb2, length(p) AS SHORTEST_PATH ORDER BY SHORTEST_PATH ASC;"""

    parameters = {"chosen_name_list": chosen_name_list}
    shortest_paths = graph.run(neo4j_query, parameters).to_data_frame()
    st.dataframe(shortest_paths)

    neo4j_query = f"""MATCH (fb:FB_account)-[r:HAS_SOURCE|HAS_TARGET*1..2]->(other_fb:FB_account)
    WHERE
    ID(fb)<>ID(other_fb) AND
    SIZE(apoc.coll.intersection([fb.first_name, fb.second_name], $chosen_name_list)) > 0
    RETURN fb.facebookID AS facebook, other_fb.facebookID AS linked_facebook"""
    linked_accounts = graph.run(neo4j_query, parameters).to_data_frame()
    st.dataframe(linked_accounts)
# df2 = pd.DataFrame(linked_accounts.labels.tolist(), index= linked_accounts.index)
# linked_accounts['labels'].apply(lambda x: 'FB_target' in x)
# linked_accounts.apply(lambda x: [1, 2], axis=1)
# Store the initial value of widgets in session state
# if "visibility" not in st.session_state:
#     st.session_state.visibility = "visible"
#     st.session_state.disabled = False
#
# col1, col2 = st.columns(2)
#
# with col1:
#     st.checkbox("Disable text input widget", key="disabled")
#     st.radio(
#         "Set text input label visibility 👉",
#         key="visibility",
#         options=["visible", "hidden", "collapsed"],
#     )
#     st.text_input(
#         "Placeholder for the other text input widget",
#         "This is a placeholder",
#         key="placeholder",
#     )
#
# with col2:
#     text_input = st.text_input(
#         "Enter some text 👇",
#         label_visibility=st.session_state.visibility,
#         disabled=st.session_state.disabled,
#         placeholder=st.session_state.placeholder,
#     )
#
#     if text_input:
#         st.write("You entered: ", text_input)
