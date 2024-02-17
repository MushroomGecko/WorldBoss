from flask import Flask, render_template, request, session, redirect
from werkzeug.utils import secure_filename
import os
import json
import hashlib
import random
from flask_sock import Sock
import time
import threading

CLIENT_ID = 0
CLIENT_USERNAME = 1
CLIENT_MULTI_CLICKS = 2
CLIENT_CPS = 3
CLIENT_SINGLE_CLICKS = 4
CLIENT_CURRENT_BOSS = 5
CLIENT_BOSS_HEALTH = 6
CLIENT_BOSS_PATH = 7

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "files/"
app.config["SECRET_KEY"] = str(os.urandom(random.randrange(4092)))
app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
sock = Sock(app)

client_list = []
json_lock = threading.Lock()
leave_lock = threading.Lock()

click_value = 0
current_boss = ""
boss_path = ""
boss_health = 0


@app.route('/', methods=['GET', 'POST'])
def index():
    print(session)
    if request.method == "POST":
        print("posted")
        if request.form.get('single'):
            return render_template('single_index.html', user=session['username'])
        if request.form.get('multi'):
            return render_template('multi_index.html', user=session['username'])
    if 'username' in session and session['username'].lower() not in [client[CLIENT_USERNAME].lower() for client in
                                                                     client_list]:
        return render_template('multi_index.html', user=session['username'])
    else:
        return redirect('/login')


@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    if request.method == "POST":
        # Get user inputs
        username = secure_filename(str(request.form.get('username')))
        password = secure_filename(str(request.form.get('password')))

        if username == '':
            print("Blank name")
            return render_template('signup.html')

        # Checks username and passwords for issues
        list_names = os.listdir('users/')
        if username.lower() in list_names or username == '':
            print("Duplicate or blank name")
            return render_template('signup.html')
        if len(password) > 64 or len(password) == 0:
            print("Password needs to be < 64 and > 0")
            return render_template('signup.html')
        print("Success")
        session["username"] = username
        print(session["username"])
        if not os.path.exists('users/' + username.lower()):
            os.mkdir('users/' + username.lower())

        # Add username and password to Json file
        file = open('users/' + username.lower() + '/user.json', 'w')
        file.write('[\n]')
        file.close()
        with open('users/' + username.lower() + '/user.json') as json_file_user_signup:
            data_user_signup = json.load(json_file_user_signup)
        salt_file = open("salt.txt", 'r')
        salt = salt_file.readlines()[0]
        salt_file.close()
        data_user_signup.append({
            "username": username,
            "password": hashlib.sha512((password + salt).encode('UTF-8')).hexdigest(),
            "multi_clicks": 0,
            "single_clicks": 0,
            "current_boss": "",
            "boss_health": 0,
            "boss_path": ""
        })
        json_file_user_signup.close()
        with open('users/' + username.lower() + '/user.json', 'w') as json_file_user_signup:
            json.dump(data_user_signup, json_file_user_signup, indent=4, separators=(',', ': '))
        json_file_user_signup.close()
        return redirect('/')
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Handle request
    if request.method == "POST":

        # Get user inputs
        username = secure_filename(str(request.form.get('username')))
        password = secure_filename(str(request.form.get('password')))

        # Handle user login
        if len(username) != 0 and len(password) != 0:
            if username.lower() not in os.listdir('users/'):
                print("No such username")
                return render_template('login.html')
            with open('users/' + username.lower() + '/user.json') as json_file_user_login:
                data_user_login = json.load(json_file_user_login)
            json_file_user_login.close()
            for user_login in data_user_login:
                salt_file = open("salt.txt", 'r')
                salt = salt_file.readlines()[0]
                salt_file.close()
                if username.lower() in [client[CLIENT_USERNAME].lower() for client in client_list]:
                    print("can't be logged in twice")
                    return render_template('login.html')
                elif username.lower() == user_login['username'].lower() and hashlib.sha512(
                        (password + salt).encode('UTF-8')).hexdigest() == user_login['password']:
                    print("correct")
                    session["username"] = user_login['username']
                    return redirect('/')
        # if "username" not in session:
        # return render_template('login.html')

    # If user is not logged in or is logged in somewhere else
    if 'username' not in session or session['username'].lower() in [client[CLIENT_USERNAME].lower() for client in
                                                                    client_list]:
        print("not logged in or are logged in elsewhere")
        return render_template('login.html')
    # If user is logged in
    else:
        return redirect('/')


def send_value():
    global click_value
    while True:
        time.sleep(1)
        clients = client_list.copy()
        # print(clients)
        for client_object in clients:
            client_index = client_list.index(client_object)
            try:
                # Sends cps and clicks to client
                client_object[CLIENT_ID].send(json.dumps({
                    'world_clicks': click_value,
                    'clicks_per_second': client_list[client_index][CLIENT_CPS],
                    'multi_clicks': client_list[client_index][CLIENT_MULTI_CLICKS],
                    'single_clicks': client_list[client_index][CLIENT_SINGLE_CLICKS],
                    'multi_boss_name': current_boss,
                    'multi_boss_health': boss_health,
                    'multi_boss_path': boss_path,
                    'single_boss_name': client_list[client_index][CLIENT_CURRENT_BOSS],
                    'single_boss_health': client_list[client_index][CLIENT_BOSS_HEALTH],
                    'single_boss_path': client_list[client_index][CLIENT_BOSS_PATH],
                }))
                client_list[client_index][CLIENT_CPS] = 0
            except Exception:
                print("removed")
                # Store data in json file and remove client from current client_list
                leave_lock.acquire()
                write_user_clicks(client_index)
                client_list.remove(client_object)
                leave_lock.release()
                write_boss_health(boss_health)
                print(client_list)


@sock.route('/world_boss')
def receive_data(receive_client):
    global click_value
    global boss_health
    global current_boss
    global boss_path

    # Reestablishing user data is faster than writing the data, so the written data
    # is eventually overwritten by older data
    time.sleep(1)
    # print(leave_lock.locked())
    # 0
    client_sublist = [receive_client]
    list_names = os.listdir('users/')
    if str(session['username']).lower() in list_names:
        print(leave_lock.locked())
        leave_lock.acquire()
        with open('users/' + str(session['username']).lower() + '/user.json') as json_file_user_receive:
            data_user_receive = json.load(json_file_user_receive)
        json_file_user_receive.close()
        for user_receive in data_user_receive:
            if user_receive["username"] == session['username']:
                # 1
                client_sublist.append(user_receive["username"])
                # 2
                client_sublist.append(user_receive["multi_clicks"])
                # 3
                client_sublist.append(0)
                # 4
                client_sublist.append(user_receive["single_clicks"])
                # 5
                client_sublist.append(user_receive["current_boss"])
                # 6
                client_sublist.append(user_receive["boss_health"])
                # 7
                client_sublist.append(user_receive["boss_path"])
                client_list.append(client_sublist)

                if client_list[find_index(receive_client, CLIENT_ID)][CLIENT_CURRENT_BOSS] == '':
                    with open('single_bosses.json') as json_file_boss_receive:
                        data_boss_receive = json.load(json_file_boss_receive)
                    json_file_boss_receive.close()
                    client_list[find_index(receive_client, CLIENT_ID)][CLIENT_CURRENT_BOSS] = data_boss_receive[0][
                        "name"]
                    client_list[find_index(receive_client, CLIENT_ID)][CLIENT_BOSS_HEALTH] = data_boss_receive[0][
                        "health"]
                    client_list[find_index(receive_client, CLIENT_ID)][CLIENT_BOSS_PATH] = data_boss_receive[0]["path"]
                # print(leave_lock.locked())
                break
        print(leave_lock.locked())
        print(client_list)
        leave_lock.release()

    while True:
        # gets data from client
        data_user_receive = receive_client.receive()
        # print(data_user_receive)
        client_list[find_index(receive_client, CLIENT_ID)][CLIENT_CPS] += int(data_user_receive[0])
        # print(data_user_receive[2])
        # JS is stupid and arrays are dumb
        if int(data_user_receive[2]) == 0:
            boss_health -= int(data_user_receive[0])
            click_value += int(data_user_receive[0])
            client_list[find_index(receive_client, CLIENT_ID)][CLIENT_MULTI_CLICKS] += int(data_user_receive[0])
            if boss_health <= 0:
                write_boss_health(0)
                with open('multi_bosses.json') as json_file_boss_receive:
                    data_boss_receive = json.load(json_file_boss_receive)
                json_file_boss_receive.close()
                for boss_receive in data_boss_receive:
                    if boss_receive["health"] != 0:
                        current_boss = boss_receive["name"]
                        boss_health = boss_receive["health"]
                        boss_path = boss_receive["path"]
                        break
        elif int(data_user_receive[2]) == 1:
            client_list[find_index(receive_client, CLIENT_ID)][CLIENT_SINGLE_CLICKS] += int(data_user_receive[0])
            client_list[find_index(receive_client, CLIENT_ID)][CLIENT_BOSS_HEALTH] -= int(data_user_receive[0])
            if client_list[find_index(receive_client, CLIENT_ID)][CLIENT_BOSS_HEALTH] <= 0:
                client_list[find_index(receive_client, CLIENT_ID)][CLIENT_BOSS_HEALTH] = 0
                with open('single_bosses.json') as json_file_boss_receive:
                    data_boss_receive = json.load(json_file_boss_receive)
                json_file_boss_receive.close()
                for i in range(len(data_boss_receive)):
                    if data_boss_receive[i]["name"] == client_list[find_index(receive_client, CLIENT_ID)][CLIENT_CURRENT_BOSS]:
                        boss_receive = data_boss_receive[i + 1]
                        client_list[find_index(receive_client, CLIENT_ID)][CLIENT_CURRENT_BOSS] = boss_receive["name"]
                        client_list[find_index(receive_client, CLIENT_ID)][CLIENT_BOSS_HEALTH] = boss_receive["health"]
                        client_list[find_index(receive_client, CLIENT_ID)][CLIENT_BOSS_PATH] = boss_receive["path"]
                        break


@app.errorhandler(ConnectionError)
def handle_exception():
    print("Oh no someone had a poop")


def find_index(value, position):
    count = 0
    for user_find in client_list:
        if user_find[position] == value:
            return count
        count += 1
    return None


def write_boss_health(health_value):
    with open('multi_bosses.json') as json_file_boss_write_health:
        data_boss_write_health = json.load(json_file_boss_write_health)
    json_file_boss_write_health.close()
    for boss_write_health in data_boss_write_health:
        if boss_write_health["health"] != 0:
            boss_write_health["health"] = health_value
            json_lock.acquire()
            with open('multi_bosses.json', 'w') as json_file_boss_write_health:
                json.dump(data_boss_write_health, json_file_boss_write_health, indent=4, separators=(',', ': '))
            json_file_boss_write_health.close()
            json_lock.release()
            break


def write_user_clicks(client_index):
    with open('users/' + str(
            client_list[client_index][CLIENT_USERNAME]).lower() + '/user.json') as json_file_user_write_clicks:
        data_user_write_clicks = json.load(json_file_user_write_clicks)
    json_file_user_write_clicks.close()
    for user_send in data_user_write_clicks:
        if client_list[client_index][CLIENT_USERNAME] == user_send["username"]:
            user_send["multi_clicks"] = client_list[client_index][CLIENT_MULTI_CLICKS]
            user_send["single_clicks"] = client_list[client_index][CLIENT_SINGLE_CLICKS]
            user_send["current_boss"] = client_list[client_index][CLIENT_CURRENT_BOSS]
            user_send["boss_health"] = client_list[client_index][CLIENT_BOSS_HEALTH]
            user_send["boss_path"] = client_list[client_index][CLIENT_BOSS_PATH]
            # user["buffs"] = client_buffs[client_index]
            json_lock.acquire()
            with open('users/' + str(client_list[client_index][CLIENT_USERNAME]).lower() + '/user.json',
                      'w') as json_file_user_write_clicks:
                json.dump(data_user_write_clicks, json_file_user_write_clicks, indent=4, separators=(',', ': '))
            json_file_user_write_clicks.close()
            json_lock.release()
            break


def write_all_user_clicks():
    while True:
        time.sleep(60)
        clients = client_list.copy()
        for client_object in clients:
            client_index = client_list.index(client_object)
            write_user_clicks(client_index)
        write_boss_health(boss_health)
        print("wrote all user data")


if __name__ == '__main__':
    print(os.listdir('users/'))
    # Development
    listNames = os.listdir('users/')
    for curr_username in listNames:
        with open('users/' + curr_username + '/user.json') as json_file_users:
            user_data = json.load(json_file_users)
        json_file_users.close()
        for user in user_data:
            click_value += user["multi_clicks"]
        json_file_users.close()
    with open('multi_bosses.json') as json_file_bosses:
        boss_data = json.load(json_file_bosses)
    for boss in boss_data:
        if boss["health"] != 0:
            current_boss = boss["name"]
            boss_health = boss["health"]
            boss_path = boss["path"]
            break

    t1 = threading.Thread(target=send_value)
    t1.daemon = True
    t1.start()
    t2 = threading.Thread(target=write_all_user_clicks)
    t2.daemon = True
    t2.start()

    app.run(debug=True, host="0.0.0.0", port=25565, threaded=True)
    # socketio.run(app, allow_unsafe_werkzeug=True)
    # Production
    # from waitress import serve
    module: app
    # serve(app, host="0.0.0.0", port=25565)
