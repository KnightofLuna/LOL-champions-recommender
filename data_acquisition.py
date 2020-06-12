import warnings
warnings.filterwarnings('ignore')

import requests
import bs4
import pandas as pd
import numpy as np
import re
from PIL import Image
from io import BytesIO
from IPython.core.display import HTML

def process_bar(percent, start_str='', end_str='100%', total_length=0):
    """A function used to visualize the process of web scrapping."""
    bar = ''.join(["\033[31m%s\033[0m"%'   '] * int(percent * total_length)) + ''
    bar = '\r' + start_str + bar.ljust(total_length) + ' {:0>4.1f}%|'.format(percent*100) + end_str
    print(bar, end='', flush=True)


"""web scrapping"""
baseurl = 'https://gol.gg/tournament/list/region-ALL/league-1/'
indexPage = requests.get(baseurl)
Soup = bs4.BeautifulSoup(indexPage.text)
href = Soup.select('tr > td > a')
href = [x.get('href') for x in href]
href = href[:href.index('./tournament-stats/LEC%20Spring%202019/')]
href = [x.replace('.', 'https://gol.gg/tournament') for x in href]

match_summary_href = []
for url in href:
    page = requests.get(url)
    soup = bs4.BeautifulSoup(page.text)
    href2 = soup.select('tr > td > a')
    href2 = [x.get('href') for x in href2]
    href2 = [x for x in href2 if 'page-summary' in x]
    match_summary_href.extend(href2)
    process_bar((href.index(url)+1)/len(href))

match_summary_href = [x.replace('..','https://gol.gg') for x in match_summary_href]

target_indicator = ['Role','Kills','Deaths','Assists','CSM','GPM','DPM','Total heal','Total damage taken']
n_href = len(match_summary_href)
data = []
for url in match_summary_href:
    page = requests.get(url)
    soup = bs4.BeautifulSoup(page.text)
    rd = soup.select('h1')
    rd = [x.getText() for x in rd]
    result = [x for x in rd if x == "WIN" or x == "LOSS"]
    gametime = [x for x in rd if ":" in x]  
    page_game = soup.select('li[class="nav-item game-menu-button"] > a')
    page_game = [x.get('href') for x in page_game][1:]
    fullstats = [x.replace('..','https://gol.gg').replace('page-game','page-fullstats') for x in page_game]
    for i in range(len(gametime)):
        team1_data, team2_data = [], []
        game_id = fullstats[i].split('/')[-3]
        for _ in range(5):
            team1_data.append([game_id, gametime[i], result[i*2]])
            team2_data.append([game_id, gametime[i], result[i*2+1]])
        team1_data.extend(team2_data)
        page = requests.get(fullstats[i])
        soup = bs4.BeautifulSoup(page.text)
        td = soup.select('td')
        td = [x.getText() for x in td]
        th = soup.select('th > img')
        if len(th) == 0:
            continue
        name = [x.get('alt') for x in th]
        for i in range(10):
            team1_data[i].append(name[i])    
        for indicator in target_indicator:
            index_indicator = td.index(indicator)
            indicator_value = td[index_indicator + 1: index_indicator + 11]
            for i in range(10):
                team1_data[i].append(indicator_value[i]) 
        data.extend(team1_data)
        process_bar((match_summary_href.index(url)+1)/n_href)

# store the data into pd.DataFrame
data_df = pd.DataFrame(data, columns=['GameID','Game time','Result','Champion']+target_indicator)

"""Data cleaning"""
def trans_time(x):
    m = pd.to_numeric(x.split(':')[0])
    s = pd.to_numeric(x.split(':')[-1])
    return round(m + s / 60, 2)

data_df['Game time'] = data_df['Game time'].map(trans_time)
for col in data_df.columns[5:]:
    data_df[col] = pd.to_numeric(data_df[col])
    if col in ['Kills','Deaths','Assists','Total heal','Total damage taken']:
        data_df[col] = data_df[col] / data_df['Game time']
data_df.columns = ['GameID','Game time','Result','Champion','Role','KillsPM','DeathsPM','AssistsPM','CSM','GPM','DPM','HPM','DTPM']

data_df['Champion'][data_df['Champion'] == 'Kai'] = 'Kaisa'
data_df['Champion'][data_df['Champion'] == 'Kha'] = 'KhaZix'
data_df['Champion'][data_df['Champion'] == 'Rek'] = 'RekSai'
data_df['Champion'][data_df['Champion'] == 'Kog'] = 'KogMaw'
data_df['Champion'][data_df['Champion'] == 'Cho'] = 'Chogath'

# store the data to drive
data_df.to_csv('game_data.csv', index=False)

"""Data overview"""
def img_url(x):
    x = x.replace(' ','')
    url = 'https://gol.gg/_img/champions_icon/' + x + '.png'
    return url

def path_to_image_html(path):
    base = r'<img src="%s" >'
    return base %(path)

champion_img = data_df['Champion'].map(img_url)
data_df.insert(4, value=champion_img, column='Photo')

data_df2 = data_df.set_index(['GameID','Game time', 'Result','Champion'])

pd.set_option('max_colwidth', -1)
HTML(data_df2.head(20).to_html(formatters={'Photo':path_to_image_html}, escape=False))

