def login():
    user = validate_user()
    create_session(user)

def validate_user():
    data = db_check()
    log_attempt()
    return data