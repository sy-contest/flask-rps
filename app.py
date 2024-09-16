from flask import Flask, render_template, request, session, send_from_directory
import pusher
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'secret!')

# Initialize Pusher client
pusher_client = pusher.Pusher(
    app_id=os.getenv('PUSHER_APP_ID'),
    key=os.getenv('PUSHER_KEY'),
    secret=os.getenv('PUSHER_SECRET'),
    cluster=os.getenv('PUSHER_CLUSTER'),
    ssl=True
)

games = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        room = request.form['room']
        if room in games and len(games[room]['players']) >= 2:
            return "Room is full. Please choose another room."
        session['username'] = username
        session['room'] = room
        return render_template('game.html', 
                               username=username, 
                               room=room, 
                               pusher_key=os.getenv('PUSHER_KEY'),
                               pusher_cluster=os.getenv('PUSHER_CLUSTER'))
    return render_template('index.html')

@app.route('/join', methods=['POST'])
def join():
    username = session.get('username')
    room = session.get('room')
    if room not in games:
        games[room] = {'players': [], 'choices': {}, 'scores': {}}
    if len(games[room]['players']) >= 2:
        pusher_client.trigger(room, 'room_full', {})
        return {'status': 'error', 'message': 'Room is full'}
    if username not in games[room]['players']:
        games[room]['players'].append(username)
        games[room]['scores'][username] = 0
    pusher_client.trigger(room, 'player_joined', {'username': username, 'players': games[room]['players']})
    pusher_client.trigger(room, 'update_scores', games[room]['scores'])
    if len(games[room]['players']) == 2:
        pusher_client.trigger(room, 'start_game', {'players': games[room]['players']})
    return {'status': 'success', 'players': games[room]['players']}

@app.route('/make_move', methods=['POST'])
def make_move():
    username = session.get('username')
    room = session.get('room')
    choice = request.json['choice']
    games[room]['choices'][username] = choice
    if len(games[room]['choices']) == 2:
        process_round(room)
    elif len(games[room]['choices']) == 1 and games[room].get('timer_ended', False):
        process_round(room)
    return {'status': 'success'}

@app.route('/no_choice', methods=['POST'])
def no_choice():
    username = session.get('username')
    room = session.get('room')
    games[room]['timer_ended'] = True
    if len(games[room]['choices']) == 1:
        process_round(room)
    elif len(games[room]['choices']) == 0:
        result = {'result': 'Tie! No one made a choice.', 'choices': {}, 'winner': None}
        pusher_client.trigger(room, 'game_result', result)
        pusher_client.trigger(room, 'update_scores', games[room]['scores'])
        games[room]['choices'] = {}
        games[room]['timer_ended'] = False
        if not check_game_end(room):
            pusher_client.trigger(room, 'start_round', {})
    return {'status': 'success'}

def process_round(room):
    if len(games[room]['choices']) == 2:
        result = determine_winner(games[room]['choices'])
    else:
        player_who_chose = list(games[room]['choices'].keys())[0]
        result = {'result': f'{player_who_chose} wins! The other player didn\'t choose.', 'choices': games[room]['choices'], 'winner': player_who_chose}
    
    update_scores(room, result)
    pusher_client.trigger(room, 'game_result', result)
    pusher_client.trigger(room, 'update_scores', games[room]['scores'])
    games[room]['choices'] = {}
    games[room]['timer_ended'] = False
    if not check_game_end(room):
        pusher_client.trigger(room, 'start_round', {})

def determine_winner(choices):
    players = list(choices.keys())
    p1, p2 = players[0], players[1]
    if choices[p1] == choices[p2]:
        return {'result': 'Tie!', 'choices': choices, 'winner': None}
    elif (choices[p1] == 'rock' and choices[p2] == 'scissors') or \
         (choices[p1] == 'paper' and choices[p2] == 'rock') or \
         (choices[p1] == 'scissors' and choices[p2] == 'paper'):
        return {'result': f'{p1} wins this round!', 'choices': choices, 'winner': p1}
    else:
        return {'result': f'{p2} wins this round!', 'choices': choices, 'winner': p2}

def update_scores(room, result):
    if result['winner']:
        games[room]['scores'][result['winner']] += 1

def check_game_end(room):
    for player, score in games[room]['scores'].items():
        if score >= 3:
            pusher_client.trigger(room, 'game_over', {'winner': player})
            games[room]['scores'] = {p: 0 for p in games[room]['scores']}
            pusher_client.trigger(room, 'update_scores', games[room]['scores'])
            return True
    return False

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)