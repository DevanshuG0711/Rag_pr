def login():
    validate_user()
    create_session()

def validate_user():
    db_check()

def db_check():
    pass

def create_session():
    pass



# from app.services.call_graph_query import build_graph, get_callees, get_callers
# from app.services.call_graph_query import build_graph, expand_with_graph


# call_graph = {
#     "login": ["validate_user", "create_session"],
#     "validate_user": ["db_check"],
#     "db_check": [],
#     "create_session": []
# }

# build_graph(call_graph)

# functions = ["login"]

# print(expand_with_graph([], max_depth=2))

# expanded = expand_with_graph(["login"], max_depth=1)
# print(expand_with_graph(["unknown"], max_depth=2))
# print("Expanded:", expanded)
