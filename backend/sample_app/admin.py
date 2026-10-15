from sample_app.auth import verify_token

def delete_user(request, user_id):
    if verify_token(request["token"]):
        return {"deleted": user_id}
    return {"error": "unauthorized"}