from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from datetime import datetime, timedelta
import uuid

template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.urandom(24)
DATABASE = 'quiz_data3.db'
QUIZ_DURATION_SECONDS = 60 * 5  # Ví dụ: 5 phút
QUIZ_DURATION_MINUTES = QUIZ_DURATION_SECONDS // 60

# Dictionary để lưu trữ kết quả tạm thời trên server (tránh cookie quá lớn)
QUIZ_RESULTS_CACHE = {}

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def load_questions():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, question, option_a, option_b, option_c, answer FROM questions")
    questions = cursor.fetchall()
    db.close()
    return questions

def calculate_score(questions, user_answers):
    score = 0
    results = {}
    for question in questions:
        question_id = question['id']
        correct_answer = question['answer'].lower()
        user_answer = user_answers.get(str(question_id), '').lower()
        is_correct = user_answer == correct_answer
        results[question_id] = {
            'question_text': question['question'],
            'options': {'a': question['option_a'], 'b': question['option_b'], 'c': question['option_c']},
            'user_answer': user_answer.upper(),
            'correct_answer': correct_answer.upper(),
            'is_correct': is_correct
        }
        if is_correct:
            score += 1
    return score, results

@app.route('/')
def index():
    questions = load_questions()
    total_questions = len(questions)
    quiz_duration_minutes = QUIZ_DURATION_SECONDS // 60
    return render_template('index.html', total_questions=total_questions, quiz_duration_minutes=quiz_duration_minutes)

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    questions = load_questions()
    if not questions:
        return "Không có câu hỏi nào trong cơ sở dữ liệu."
    total_questions = len(questions)

    if 'start_time' not in session:
        session['start_time'] = datetime.utcnow()
        session['end_time'] = session['start_time'] + timedelta(seconds=QUIZ_DURATION_SECONDS)
        session['current_question_index'] = 0
        session['answers'] = {}
        session.pop('quiz_results_id', None)
        session.pop('quiz_score', None)
        session.pop('quiz_total', None)

    current_index = session['current_question_index']
    current_question = questions[current_index]
    end_time = session['end_time']
    now_utc = datetime.utcnow().replace(tzinfo=None)
    end_time_naive = session['end_time'].replace(tzinfo=None)
    time_remaining = (end_time_naive - now_utc).total_seconds()


    if request.method == 'POST':
        action = request.form.get('action')
        selected_answer = request.form.get(str(current_question['id']))

        if selected_answer:
            session['answers'][str(current_question['id'])] = selected_answer

        if action == 'next':
            session['current_question_index'] = min(current_index + 1, total_questions - 1)
        elif action == 'prev':
            session['current_question_index'] = max(current_index - 1, 0)
        elif action.startswith('goto_'):
            try:
                goto_index = int(action.split('_')[1])
                session['current_question_index'] = min(max(goto_index, 0), total_questions - 1)
            except ValueError:
                pass
        elif action == 'submit' or time_remaining <= 0:
            score, results = calculate_score(questions, session.get('answers', {}))
            results_id = str(uuid.uuid4())
            QUIZ_RESULTS_CACHE[results_id] = results
            session['quiz_results_id'] = results_id
            session['quiz_score'] = score
            session['quiz_total'] = total_questions
            session.pop('start_time', None)
            session.pop('end_time', None)
            session.pop('current_question_index', None)
            session.pop('answers', None)
            return redirect(url_for('results'))

        return redirect(url_for('quiz'))

    else:
        user_answer = session['answers'].get(str(current_question['id']))
        return render_template('quiz_paged.html',
                               question=current_question,
                               question_number=current_index + 1,
                               total_questions=total_questions,
                               user_answer=user_answer,
                               time_remaining=int(time_remaining))

@app.route('/results')
def results():
    score = session.get('quiz_score')
    total = session.get('quiz_total')
    results_id = session.get('quiz_results_id')
    results = QUIZ_RESULTS_CACHE.get(results_id, {})
    return render_template('results.html', score=score, total=total, results=results)

@app.route('/results/<int:question_id>')
def view_result_detail(question_id):
    results_id = session.get('quiz_results_id')
    results = QUIZ_RESULTS_CACHE.get(results_id)
    if results and question_id in results:
        result = results[question_id]
        return render_template('result_detail.html', result=result)
    else:
        return "Không tìm thấy thông tin chi tiết cho câu hỏi này."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Sử dụng cổng do Render cung cấp
    app.run(debug=False, host='0.0.0.0', port=port)
