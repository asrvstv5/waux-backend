from flask import request, jsonify
from functools import wraps
import jwt

SECRET_KEY = 'super-secret-key'

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 403

        try:
            # Ensure token is in the format "Bearer <token>"
            token = token.split(" ")[1] if "Bearer" in token else token

            # Decode the token
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            
            # Extract user details
            current_user = {
                "user_id": data["user_id"],
                "username": data["username"]
            }
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 403
        except jwt.InvalidTokenError as e:
            return jsonify({'message': 'Token is invalid!', 'error': str(e)}), 403

        # Pass `user_id` and `username` to the decorated function
        return f(current_user["user_id"], current_user["username"], *args, **kwargs)

    return decorated