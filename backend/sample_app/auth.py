def verify_token(token, require_admin):
    """Returns True if the token is valid."""
    if require_admin:
        return token == "admin-token"
    return token == "secret-token"