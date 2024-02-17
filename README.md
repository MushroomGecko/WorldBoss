# WorldBoss
A clicker-style game where players come together to take down a common foe!

WorldBoss is hosted on port 25565 and the dependencies include flask, flask_sock, werkzeug, os, json, hashlib, random, time, and threading.
There are two default users; user1 and user2. user1 has the password "12345" and user2 has the password "54321".
You can add new bosses or modify existing bosses by editing multi_bosses.json and single_bosses.json. Add the picture on any new bosses in the "static" directory.
Passwords are salted with the salt found in salt.txt and are hashed with SHA512.
