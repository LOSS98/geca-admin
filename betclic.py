from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException

from bs4 import BeautifulSoup, Comment
from datetime import datetime, timedelta
import time



def clean_text(text):
    text = text.replace('\n', '').replace('\r', '').replace('\t', '')
    text = text.replace(',', '.').strip()
    text = ' '.join(text.split())
    text = text.replace('\xa0', ' ').strip()
    return text

def convert_to_date(date_str):
    today = datetime.today().date()
    if date_str.lower() == "aujourd'hui":
        return today.strftime('%Y-%m-%d')
    elif date_str.lower() == "demain":
        return (today + timedelta(days=1)).strftime('%Y-%m-%d')
    elif date_str.lower() == "après-demain":
        return (today + timedelta(days=2)).strftime('%Y-%m-%d')
    else:
        try:
            return datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Format de date non reconnu: {date_str}")


def check_filter(data, marketFilter):
    def check_odd(odd, min_odd, max_odd):
        if min_odd is not None and odd < min_odd:
            return False
        if max_odd is not None and odd > max_odd:
            return False
        return True

    def check_date(date_str, from_date, to_date):
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        if from_date is not None and date_obj < datetime.strptime(from_date, '%Y-%m-%d'):
            return False
        if to_date is not None and date_obj > datetime.strptime(to_date, '%Y-%m-%d'):
            return False
        return True

    condition1 = (
            check_odd(data['teamA']['odd'], marketFilter['oddA']['min'], marketFilter['oddA']['max']) and
            check_odd(data['teamB']['odd'], marketFilter['oddB']['min'], marketFilter['oddB']['max'])
    )

    condition2 = (
            check_odd(data['teamA']['odd'], marketFilter['oddB']['min'], marketFilter['oddB']['max']) and
            check_odd(data['teamB']['odd'], marketFilter['oddA']['min'], marketFilter['oddA']['max'])
    )

    date_condition = check_date(data['date'], marketFilter['fromDate'], marketFilter['toDate'])

    return date_condition and (condition1 or condition2)

defaultFilter ={
            'oddA': {
                'min' : None,
                'max' : None
            },
            'oddB': {
                    'min' : None,
                    'max' : None
                },
            'coteDraw': {
                        'min' : None,
                        'max' : None
                    },
            'toDate': None,
            'fromDate': None
        }

def scrape_html(marketFilter=defaultFilter, url='https://www.betclic.fr/football-s1'):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    chrome_driver_path = "./chromedriver"
    driver = webdriver.Chrome(service=Service(chrome_driver_path), options=options)

    driver.get(url)

    def handle_cookies(driver):
        try:
            cookies_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continuer sans accepter')]")
            cookies_button.click()
        except NoSuchElementException:
            pass

    handle_cookies(driver)

    def scroll_to_end(driver):
        SCROLL_PAUSE_TIME = 1
        last_height = driver.execute_script("return document.body.scrollHeight")

        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)
            handle_cookies(driver)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    scroll_to_end(driver)

    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, 'html.parser')
    eventsList = soup.find('div', attrs={'infinitescroll': True}).select('.verticalScroller_list')[0]
    eventsByDays = eventsList.find_all('div', class_='groupEvents')

    while len(eventsByDays[0].select('.is-live')) > 0:
        eventsByDays.pop(0)

    events = []
    for dayEvents in eventsByDays:
        eventDay = convert_to_date(dayEvents.select_one('.groupEvents_headTitle').text)
        for event in dayEvents.select('.cardEvent'):
            link = 'https://www.betclic.fr/'+event.get('href')
            eventTime = clean_text(event.select_one('.scoreboard_hour').text)
            competition = clean_text(
                event.select_one('.breadcrumb_item.is-ellipsis').find('span', class_='breadcrumb_itemLabel').text)
            market = event.select_one('.market_odds').find('div', class_='btnWrapper').find_all('button')
            if len(market) != 3:
                break
            teams_and_odds = []
            for button in market:
                spans = button.find_all('span', class_=['is-top'])
                team_name = ''.join(clean_text(span.text) for span in spans)
                odds = float(clean_text(button.find_all('span', class_='btn_label')[1].text))
                teams_and_odds.append((team_name, odds))
            data = {
                'competition': competition,
                'link': link,
                'date': eventDay,
                'time': eventTime,
                'teamA': {
                    'name': teams_and_odds[0][0],
                    'odd': teams_and_odds[0][1]
                },
                'teamB': {
                    'name': teams_and_odds[2][0],
                    'odd': teams_and_odds[2][1]
                },
                'draw': {
                    'name': teams_and_odds[1][0],
                    'odd': teams_and_odds[1][1]
                }
            }
            if check_filter(data, marketFilter):
                events.append(data)
    return events