from sample_app.auth import verify_token

def get_profile(request):
    if not verify_token(request["token"]):
        return {"error": "unauthorized"}
    return {"user": "demo"}