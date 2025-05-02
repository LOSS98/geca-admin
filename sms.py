import psycopg2
import asyncio
import aiohttp
import urllib.parse
import time


async def send_message(session, email, phone, fname, api_key):
    """Envoie un message à un utilisateur spécifique sans attendre la réponse"""
    message = f"""
Deso je fais chier avec mes messages, j'essaie d'en envoyer le moins possible
🚀 Bonjoouuur {fname} !
Ceci est un message (le 4e) de TEST groupé pour vérifier que notre API fonctionne ! 🎉 
Si tu recevez ce message, c'est que tout fonctionne. 🔥
Bonne journée et bon H5 !
- Khaliloss"""

    encoded_message = urllib.parse.quote(message)
    api_url = f"http://api.textmebot.com/send.php?recipient={phone}&apikey={api_key}&text={encoded_message}"

    try:

        await session.get(api_url, ssl=True, timeout=aiohttp.ClientTimeout(total=1))
        print(f"Message envoyé à {fname} ({email}, {phone})")
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi à {fname} ({email}, {phone}): {str(e)}")
        return False


async def send_messages_async():

    db_config = {
        'dbname': 'postgres_geca_db',
        'user': 'khalil',
        'password': 'Kh4lil9870720406*',
        'host': '51.38.83.204',
        'port': '1125'
    }


    api_key = "UDvABgmTtdWC"
    delay_seconds = 6


    conn = None
    try:

        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()


        cursor.execute("SELECT email, phone, fname FROM users WHERE phone IS NOT NULL")
        users = cursor.fetchall()

        print(
            f"Envoi de messages à {len(users)} utilisateurs avec un délai de {delay_seconds} secondes entre chaque message...")


        timeout = aiohttp.ClientTimeout(total=300)
        connector = aiohttp.TCPConnector(limit=10)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:

            results = []
            for email, phone, fname in users:

                result = await send_message(session, email, phone, fname, api_key)
                results.append(result)


                print(f"Attente de {delay_seconds} secondes avant le prochain envoi...")
                await asyncio.sleep(delay_seconds)


            success_count = sum(1 for r in results if r is True)
            error_count = len(results) - success_count

            print(f"\nRésumé: {success_count} messages envoyés avec succès, {error_count} échecs")

    except Exception as e:
        print(f"Erreur de connexion à la base de données: {str(e)}")

    finally:

        if conn is not None:
            cursor.close()
            conn.close()
            print("Connexion à la base de données fermée.")



def send_messages_to_users():
    asyncio.run(send_messages_async())


if __name__ == "__main__":
    send_messages_to_users()