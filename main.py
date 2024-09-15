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
        result = determine_winner(games[room]['choices'])
        update_scores(room, result)
        emit('game_result', result, room=room)
        emit('update_scores', games[room]['scores'], room=room)
        games[room]['choices'] = {}
        check_game_end(room)

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

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    socketio.run(app, debug=True)