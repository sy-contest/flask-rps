from flask import Flask, render_template, request, session, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, emit
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

games = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        room = request.form['room']
        if room in games and len(games[room]['players']) >= 2:
            return "Room is full. Please choose another room."
        session['username'] = username
        return render_template('game.html', username=username, room=room)
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    if room not in games:
        games[room] = {'players': [], 'choices': {}, 'scores': {}}
    if len(games[room]['players']) >= 2:
        emit('room_full')
        return
    join_room(room)
    games[room]['players'].append(username)
    games[room]['scores'][username] = 0
    emit('status', {'msg': f'{username} has joined the room.'}, room=room)
    emit('update_scores', games[room]['scores'], room=room)
    if len(games[room]['players']) == 2:
        emit('start_game', {'players': games[room]['players']}, room=room)

@socketio.on('make_move')
def on_move(data):
    username = data['username']
    room = data['room']
    choice = data['choice']
    games[room]['choices'][username] = choice
    if len(games[room]['choices']) == 2:
        process_round(room)
    elif len(games[room]['choices']) == 1 and games[room].get('timer_ended', False):
        process_round(room)

@socketio.on('no_choice')
def on_no_choice(data):
    username = data['username']
    room = data['room']
    games[room]['timer_ended'] = True
    if len(games[room]['choices']) == 1:
        process_round(room)
    elif len(games[room]['choices']) == 0:
        result = {'result': 'Tie! No one made a choice.', 'choices': {}, 'winner': None}
        emit('game_result', result, room=room)
        emit('update_scores', games[room]['scores'], room=room)
        games[room]['choices'] = {}
        games[room]['timer_ended'] = False
        if not check_game_end(room):
            socketio.emit('start_round', room=room)

def process_round(room):
    if len(games[room]['choices']) == 2:
        result = determine_winner(games[room]['choices'])
    else:
        player_who_chose = list(games[room]['choices'].keys())[0]
        result = {'result': f'{player_who_chose} wins! The other player didn\'t choose.', 'choices': games[room]['choices'], 'winner': player_who_chose}
    
    update_scores(room, result)
    emit('game_result', result, room=room)
    emit('update_scores', games[room]['scores'], room=room)
    games[room]['choices'] = {}
    games[room]['timer_ended'] = False
    if not check_game_end(room):
        socketio.emit('start_round', room=room)

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
            emit('game_over', {'winner': player}, room=room)
            games[room]['scores'] = {p: 0 for p in games[room]['scores']}
            emit('update_scores', games[room]['scores'], room=room)
            return True
    return False

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)