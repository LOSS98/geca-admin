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
        # Envoie la requête sans attendre la réponse
        await session.get(api_url, ssl=True, timeout=aiohttp.ClientTimeout(total=1))
        print(f"Message envoyé à {fname} ({email}, {phone})")
        return True
    except Exception as e:
        print(f"Erreur lors de l'envoi à {fname} ({email}, {phone}): {str(e)}")
        return False


async def send_messages_async():
    # Configuration de la base de données
    db_config = {
        'dbname': 'postgres_geca_db',
        'user': 'khalil',
        'password': 'Kh4lil9870720406*',
        'host': '51.38.83.204',
        'port': '1125'
    }

    # Configuration de l'API
    api_key = "UDvABgmTtdWC"
    delay_seconds = 6  # Délai recommandé pour éviter d'être bloqué par WhatsApp

    # Connexion à la base de données
    conn = None
    try:
        # Connexion à la base de données
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        # Récupération de tous les numéros de téléphone
        cursor.execute("SELECT email, phone, fname FROM users WHERE phone IS NOT NULL")
        users = cursor.fetchall()

        print(
            f"Envoi de messages à {len(users)} utilisateurs avec un délai de {delay_seconds} secondes entre chaque message...")

        # Création d'une session HTTP pour toutes les requêtes
        timeout = aiohttp.ClientTimeout(total=300)  # Augmenté pour tenir compte des délais
        connector = aiohttp.TCPConnector(limit=10)  # Réduit le nombre de connexions simultanées

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            # Envoi séquentiel avec délai pour respecter les recommandations WhatsApp
            results = []
            for email, phone, fname in users:
                # Envoi du message
                result = await send_message(session, email, phone, fname, api_key)
                results.append(result)

                # Attendre avant d'envoyer le prochain message
                print(f"Attente de {delay_seconds} secondes avant le prochain envoi...")
                await asyncio.sleep(delay_seconds)

            # Compter les succès et les échecs
            success_count = sum(1 for r in results if r is True)
            error_count = len(results) - success_count

            print(f"\nRésumé: {success_count} messages envoyés avec succès, {error_count} échecs")

    except Exception as e:
        print(f"Erreur de connexion à la base de données: {str(e)}")

    finally:
        # Fermeture de la connexion à la base de données
        if conn is not None:
            cursor.close()
            conn.close()
            print("Connexion à la base de données fermée.")


# Point d'entrée pour exécuter la fonction asynchrone
def send_messages_to_users():
    asyncio.run(send_messages_async())


if __name__ == "__main__":
    send_messages_to_users()