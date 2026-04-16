def create_session(user):
    token = generate_token(user)
    save_session(token)

def save_session(token):
    pass