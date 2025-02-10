import sqlite3
import requests


def send_whatsapp_message(api_key, phone_number, message):
    url = f"https://api.callmebot.com/whatsapp.php"
    params = {
        "phone": phone_number,
        "text": message,
        "apikey": api_key
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        print("Message envoyé avec succès ! ✅")
    else:
        print(f"Erreur {response.status_code}: {response.text}")

def get_notification_tokens(db_path):
    tokens = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT fname, lname, notification_token, phone FROM users")
        rows = cursor.fetchall()

        tokens = [{'fname' : row[0], 'lname' : row[1], 'token' : row[2], 'phone' : '+33'+row[3][1:]} for row in rows if row[2] is not None]

    except sqlite3.Error as e:
        print(f"Erreur SQLite: {e}")
    finally:
        if conn:
            conn.close()

    return tokens


db_path = "instance/gecaDB.db"
tokens = get_notification_tokens(db_path)

for token in tokens :
    if True:
        message = 'Hello world !\nGECA test message to ' + token['fname'] + ' ' + token['lname'] + ' 😎\n_texte italique_ \n*texte gras* \n~texte barré~ \nAccents éÉèÈêÊîÎàÀçÇùÙ \n-Khaliloss'
        send_whatsapp_message(token['token'], token['phone'], message)
