"""Exercise: write find_nodes() yourself.

Run:  python exercise_find_nodes.py
Goal: all 4 checks at the bottom pass.
"""
import networkx as nx

# A tiny fake call graph with 4 functions (same shape as CodeMind's real graph).
# Node id = "file::qualname". Each node also stores its short name and qualname.
graph = nx.DiGraph()
graph.add_node("sessions.py::Session.send", name="send", qualname="Session.send")
graph.add_node("adapters.py::HTTPAdapter.send", name="send", qualname="HTTPAdapter.send")
graph.add_node("sessions.py::Session.request", name="request", qualname="Session.request")
graph.add_node("utils.py::get_netrc_auth", name="get_netrc_auth", qualname="get_netrc_auth")


def find_nodes(name):
    """Return every node id that matches `name`, sorted.

    `name` can be:
      - a full id         "sessions.py::Session.send"  -> just that one node
      - a qualified name  "Session.send"               -> nodes whose qualname matches
      - a short name      "send"                       -> nodes whose name matches
    """
    # Step 1: if `name` is already a full node id, return a list with only it.
    #         Hint: graph.has_node(name) gives True / False.

    # Step 2: make an empty list. Loop over every node and its data:
    #             for node_id, data in graph.nodes(data=True):
    #         If data["name"] == name OR data["qualname"] == name,
    #         add node_id to the list (hint: .append()).

    # Step 3: return the list, sorted (hint: sorted(...)).
    if graph.has_node(name):
       return[name]
    matches=[]
    for node_id,data in graph.nodes (data=True):
        if data["name"]==name or data["qualname"]==name:
            matches.append(node_id)
    return sorted(matches)

                                   
      


# ---- Checks: don't change these ----
assert find_nodes("sessions.py::Session.send") == ["sessions.py::Session.send"], "check 1 failed: full id"
assert find_nodes("send") == ["adapters.py::HTTPAdapter.send", "sessions.py::Session.send"], "check 2 failed: short name"
assert find_nodes("Session.send") == ["sessions.py::Session.send"], "check 3 failed: qualified name"
assert find_nodes("websocket") == [], "check 4 failed: name that doesn't exist"
print("All 4 checks passed!")
