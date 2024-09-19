class Playlist:
    def __init__(self, author_name: str = "", session_id: str = "", current_song_id: str = ""):
        self.song_list = []  # List of SongEntry
        self.author_name = author_name
        self.current_song_id = current_song_id
        self.session_id = session_id

class Song:
    def __init__(self, uri: str = "", name: str = ""):
        self.uri = uri
        self.name = name

class SongEntry:
    def __init__(self, song: Song = None, author: str = "", id: int = None):
        self.song = song if song else Song()
        self.author = author
        self.id = id

class User:
    def __init__(self, user_id, username, email=None, isGuestUser=False):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.isGuestUser = isGuestUser

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'isGuestUser': self.isGuestUser
        }


class Session:
    def __init__(self, host: User, name: str, session_id: str):
        self.host = host
        self.name = name
        self.session_id = session_id
        self.users = [host]  # Start with host in the user list
        self.playlist = Playlist(author_name=host, session_id=session_id)


