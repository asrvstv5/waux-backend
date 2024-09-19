import uuid
import random
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from bson.objectid import ObjectId
import pymongo
import uuid
from db import client
from middlewares import token_required
# from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from models import User, Playlist, Song, SongEntry, Session
from datetime import datetime, timedelta, timezone
import jwt

db = client["waux"]
sessions_collection = db["sessions"]
users_collection = db["users"]

# Initialize Flask app
app = Flask(__name__)
socketio = SocketIO(app)

SECRET_KEY = 'super-secret-key'
# Initialize JWT manager
# jwt = JWTManager(app)

# Name generation
male_names = ["John", "Robert", "Michael", "David", "James", "Rambo"]
female_names = ["Mary", "Jennifer", "Patricia", "Linda", "Barbara", "Karen"]

# Generate random name for guest login
def generate_random_name():
    male_names = ['John', 'Paul', 'Mike', 'Jake']
    female_names = ['Sarah', 'Emily', 'Anna', 'Jessica']
    all_names = male_names + female_names
    return random.choice(all_names)

# Create JWT token
def create_jwt_token(user_id, username):
    token = jwt.encode({
        'user_id': user_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, SECRET_KEY, algorithm='HS256')
    return token

# Login API (Guest Login)
@app.route('/login', methods=['POST'])
def login():
    guest_user = request.args.get('guestUser', 'false').lower() == 'true'

    if guest_user:
        user_id = str(uuid.uuid4())  # Unique ID
        username = generate_random_name()  # Random name
        token = create_jwt_token(user_id, username)

        # Store user in MongoDB
        users_collection.insert_one({
            'user_id': user_id,
            'username': username,
            'email': None,
            'isGuestUser': True,
            'currentSession': None
        })

        return jsonify({
            'message': 'Guest login successful',
            'user_id': user_id,
            'username': username,
            'token': token
        }), 200

    return jsonify({'message': 'Login without guestUser not implemented'}), 400

# Create a session
@app.route('/session', methods=['POST'])
@token_required
def create_session(user_id, username):
    data = request.get_json()
    session_name = data.get('name')

    # Create a session object
    session_id = str(uuid.uuid4())  # Generate a unique session ID
    host = {'user_id': user_id, 'username': username}
    
    new_session = {
        'host': host,
        'name': session_name,
        'session_id': session_id,
        'users': [user_id],
        'playlist': {
            'songList': [],
            'authorName': username,
            'sessionId': session_id
        }
    }

    # Save session to MongoDB
    sessions_collection.insert_one(new_session)
    
    # Update user's currentSession to session_id
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'currentSession': session_id}}
    )

    return jsonify({
        'message': 'Session created successfully!',
        'session_id': session_id,
        'host': username
    }), 201

@app.route('/joinSession', methods=['POST'])
@token_required
def join_session(user_id, username):
    data = request.json
    session_id = data.get('session_id')

    # Fetch the session from the database
    session = sessions_collection.find_one({'session_id': session_id})

    if not session:
        return jsonify({'message': 'Session not found'}), 404

    # Check if the user is already in the session
    if user_id not in session['users']:
        # Add the user to the session
        sessions_collection.update_one(
            {'session_id': session_id},
            {'$push': {'users': user_id}}
        )

        # Update user's currentSession to the session_id
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'currentSession': session_id}}
        )

    # Fetch the updated session details to return
    updated_session = sessions_collection.find_one({'session_id': session_id})

    return jsonify({
        'message': f'User {username} joined the session',
        'session_id': updated_session['session_id'],
        'host': updated_session['host'],
        'name': updated_session['name'],
        'users': updated_session['users'],
        'playlist': updated_session['playlist']
    }), 200

# Leave a session
@app.route('/leaveSession', methods=['POST'])
@token_required
def leave_session(user_id, username):
    data = request.json
    session_id = data.get('session_id')

    session = sessions_collection.find_one({'session_id': session_id})

    if not session:
        return jsonify({'message': 'Session not found'}), 404

    if session['host']['user_id'] == user_id:
        # Host leaves, delete session
        sessions_collection.delete_one({'session_id': session_id})
    else:
        sessions_collection.update_one(
            {'session_id': session_id},
            {'$pull': {'users': user_id}}
        )

    users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'currentSession': None}}
    )

    return jsonify({'message': f'User {username} left the session'}), 200

@app.route('/user', methods=['DELETE'])
def delete_user(user_id, username):
    data = request.get_json()
    user_id_to_delete = data['user_id']

    if not user_id_to_delete:
        return jsonify({'message': 'User ID is required'}), 400

    # Find the user in the database
    user = users_collection.find_one({'user_id': user_id_to_delete})

    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Delete the user from the database
    users_collection.delete_one({'user_id': user_id_to_delete})

    return jsonify({'message': f'User {user_id_to_delete} deleted successfully'}), 200


### WebSocket events ###
# Join a session (WebSocket room)
@socketio.on('join_session')
def handle_join_session(data):
    session_id = data['session_id']
    user_id = data['user_id']
    session = sessions_collection.find_one({'session_id': session_id})

    if not session:
        emit('error', {'message': 'Session not found'})
        return

    join_room(session_id)
    emit('join_success', {'message': f'User {user_id} joined the session'}, room=session_id)

"""
{
  "session_id": "12345",  // The ID of the session to which the song is being added
  "song": {
    "uri": "spotify:track:6rqhFgbbKwnb9MLmUQDhG6",  // Song URI (Spotify, YouTube Music, etc.)
    "name": "Song Title"  // Name of the song
  },
  "author": "User1",  // The user who added the song
  "id": 104  // A unique identifier for this SongEntry (server can generate this if necessary)
}
"""
# Add a song entry
@socketio.on('add_song')
def handle_add_song(data):
    session_id = data['session_id']
    song_data = data['song']
    author = data['author']
    song_id = data.get('id')  # You can generate a unique ID here if necessary

    new_song_entry = {
        'song': {
            'uri': song_data['uri'],
            'name': song_data['name']
        },
        'author': author,
        'id': song_id
    }

    sessions_collection.update_one(
        {'session_id': session_id},
        {'$push': {'playlist.songList': new_song_entry}}
    )

    emit('song_added', new_song_entry, room=session_id)

"""
{
    "session_id": "12345",
    "id": 123
}
"""
# Delete a song entry
@socketio.on('delete_song')
def handle_delete_song(data):
    session_id = data['session_id']
    song_id = data['id']

    sessions_collection.update_one(
        {'session_id': session_id},
        {'$pull': {'playlist.songList': {'id': song_id}}}
    )

    emit('song_deleted', {'song_id': song_id}, room=session_id)

"""
{
  "session_id": "12345",  // The ID of the session to reorder songs
  "new_order": [101, 103, 102]  // The list of SongEntry IDs in the desired order
}
"""
# Reorder songs
@socketio.on('reorder_songs')
def handle_reorder_songs(data):
    session_id = data['session_id']
    new_order = data['new_order']  # List of song IDs in the new order

    session = sessions_collection.find_one({'session_id': session_id})
    updated_song_list = sorted(
        session['playlist']['songList'],
        key=lambda song: new_order.index(song['id'])
    )

    sessions_collection.update_one(
        {'session_id': session_id},
        {'$set': {'playlist.songList': updated_song_list}}
    )

    emit('songs_reordered', updated_song_list, room=session_id)

@socketio.on('update_current_song')
def handle_update_current_song(data):
    session_id = data['session_id']
    current_song_id = data['current_song_id']

    # Find the session and update the current_song_id
    result = sessions_collection.update_one(
        {'session_id': session_id},
        {'$set': {'playlist.current_song_id': current_song_id}}
    )

    # Check if the update was successful
    if result.modified_count == 1:
        # Emit an event to notify clients about the updated current song
        emit('current_song_updated', {'current_song_id': current_song_id}, room=session_id)
    else:
        # If no session was found or updated, send an error message
        emit('error', {'message': 'Failed to update the current song'}, room=session_id)

# Start the Flask-SocketIO app
if __name__ == '__main__':
    socketio.run(app, debug=True)
