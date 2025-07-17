from flask import Flask, render_template_string, request, session, redirect, url_for
import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # you can leave as it is

# Configuration
base_url = "https://app.brainyware.ai"
api_key = "YOUR_API_KEY"
headers = {
    "Authorization": api_key,
    "Content-Type": "application/json"
}
generic_chat_id = 1832 
docs_chat_id = 2282
db_chat_id = 2274


def chat(id, query):
    """Sends a API chat request based on the id of the chat and can be generic, database and docs"""
    chat_request_url = f"{base_url}/api/v2/ais/chat/{id}"
    data = {"message": query}
    
    try:
        #making chat request
        chat_request_response = requests.post(chat_request_url, json=data, headers=headers)
        chat_request_response.raise_for_status()
        result_uuid = chat_request_response.json()['data']['result_uuid']
        
        #fetching response
        max_retries = 100
        retry_count = 0
        response_request_url = f"{base_url}/api/v2/ais/chat_result/{id}?result_uuid={result_uuid}"
        while retry_count < max_retries:
            response = requests.get(response_request_url, headers=headers)
            if response.json().get('success') is True:
                return response.json()['data']['response']
            retry_count += 1
            time.sleep(1)

        return "Error generating response."
    except Exception as e:
        return f"Exception: {str(e)}"

def get_history(id):
    """Gets the history of a chat based on it's ID. In this script this ID will likely be a Generic chat. Expected return --> history:: list"""
    chat_history_url = f"{base_url}/api/v2/ais/messages/{id}"
    try:
        # making history request
        chat_history_response = requests.get(chat_history_url, headers=headers)
        if chat_history_response.status_code == 200:
            data = chat_history_response.json()
            if 'data' in data and 'messages' in data['data']:
                total_history = data['data']['messages']
                history = []
                for interaction in total_history:
                    filtered = {key: value for key, value in interaction.items() if key not in ['id', 'created_at', 'infos']}
                    history.append(filtered)
                return history  # Return filtered history
            
        # If anything goes wrong or response isn't 200
        return []  
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return []
    

@app.route("/clear")
def clear_chat():
    """This endpoint clear the Combined Chat history and clears also the Generic chat history. 
    example of endpoint: {{BASE_URL}}/clear?chat_id=1832&docs_chat_id=2282&db_chat_id=2274"""

    # Get request parameters
    chat_id = request.args.get('chat_id', type=int)
    docs_chat_id = request.args.get('docs_chat_id', type=int)
    db_chat_id = request.args.get('db_chat_id', type=int)
    # Sets an empty history on the chat
    session['chat_history'] = []
    session.modified = True
    # Resets the corresponding Generic Chat history
    requests.delete(f"{base_url}/api/v2/ais/messages/{chat_id}", headers=headers)
    # Return the current page
    return redirect(url_for('index', chat_id=chat_id, docs_chat_id=docs_chat_id, db_chat_id=db_chat_id))
    

@app.route("/chat", methods=["GET", "POST"])
def index():
    """This endpoint executes the Combined Chat based on the docs and db chat results.
    example of endpoint: {{BASE_URL}}/chat?chat_id=1832&docs_chat_id=2282&db_chat_id=2274"""
    
    # Get request parameters
    generic_chat_id = request.args.get('chat_id', type=int)
    docs_chat_id = request.args.get('docs_chat_id', type=int)
    db_chat_id = request.args.get('db_chat_id', type=int)
    
    if 'chat_history' not in session:
        session['chat_history'] = []

    if request.method == "POST":
        # Get history from the generic chat
        history = get_history(generic_chat_id)
        # gen_user_query will be used in generic and db chat, user_query will be used in docs chat
        gen_user_query = request.form["query"]  
        user_query = str(history) + "/n-----------/n" + request.form["query"]  
        # making parallel requests to db and docs chat and getting repsonses
        with ThreadPoolExecutor() as executor:
            docs_future = executor.submit(chat, docs_chat_id, user_query)
            db_future = executor.submit(chat, db_chat_id, gen_user_query) #####
            docs_chat_result = docs_future.result()  # Wait for completion
            db_chat_result = db_future.result()      # Wait for completion
        # making request to generic chat based on the db and docs results    
        gen_query = f"USA SOLO ED UNICAMENTE QUESTE INFORMAZIONI E NON USARE MAI ALTRE INFORMAZIONI:{docs_chat_result} {db_chat_result} RISPONDERE{gen_user_query}"
        generic_chat_result = chat(generic_chat_id, gen_query)
        #deleting history of the db and docs chat because they are uneccessary for the use case
        requests.delete(f"{base_url}/api/v2/ais/messages/{docs_chat_id}", headers=headers)
        requests.delete(f"{base_url}/api/v2/ais/messages/{db_chat_id}", headers=headers)
        

        # Append to the combined chat history
        session['chat_history'].append({
            'user': gen_user_query,
            'bot' : generic_chat_result
        })
        session.modified = True

    return render_template_string(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>BrainyWare Chat Interface</title>
            <style>
                body {
                    font-family: Arial;
                    margin: 0;
                    padding: 0;
                    background: #f1f1f1;
                }
                .chat-container {
                    max-width: 600px;
                    margin: auto;
                    background: white;
                    height: 90vh;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    border: 1px solid #ccc;
                    margin-top: 20px;
                }
                .chat-header {
                    padding: 10px;
                    border-bottom: 1px solid #ccc;
                    text-align: right;
                    font-weight: bold;
                }
                .messages {
                    padding: 20px;
                    overflow-y: auto;
                    flex-grow: 1;
                }
                .message {
                    margin: 10px 0;
                    clear: both;
                }
                .user {
                    text-align: right;
                }
                .bot {
                    text-align: left;
                }
                .bubble {
                    display: inline-block;
                    padding: 10px 15px;
                    border-radius: 10px;
                    max-width: 70%;
                    line-height: 1.4;
                }
                .user .bubble {
                    background-color: #add8e6;
                }
                .bot .bubble {
                    background-color: #efefef;
                }
                form {
                    display: flex;
                    padding: 10px;
                    border-top: 1px solid #ccc;
                    background: #fafafa;
                }
                input[type="text"] {
                    flex-grow: 1;
                    padding: 10px;
                    font-size: 16px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }
                button {
                    padding: 10px 15px;
                    font-size: 16px;
                    margin-left: 10px;
                    border: none;
                    background-color: #007bff;
                    color: white;
                    border-radius: 5px;
                    cursor: pointer;
                }
                button:hover {
                    background-color: #0056b3;
                }
                .clear-button {
                    display: inline-block;
                    font-size: 14px;
                    color: #007bff;
                    text-decoration: none;
                    cursor: pointer;
                    margin-right: 10px;
                }
                .clear-button:hover {
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <div class="chat-container">
               
                <div class="messages">
                    {% for msg in chat_history %}
                        <div class="message user">
                            <div class="bubble">{{ msg.user }}</div>
                        </div>
                        <div class="message bot">
                            <div class="bubble">{{ msg.bot }}</div>
                        </div>
                    {% endfor %}
                </div>
                <form method="post">
                    <input type="text" name="query" placeholder="Type your question..." required />
                    <button type="submit">Send</button>
                </form>
            </div>
        </body>
        </html>
        """,
        chat_history=session['chat_history']
    )

if __name__ == "__main__":
    app.run(debug=True)