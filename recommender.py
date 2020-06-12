import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from IPython.core.display import HTML
from itertools import product

"""Load data"""
game_data = pd.read_csv('game_data.csv')
game_data['Result'] = game_data['Result'].replace(['WIN','LOSS'], [1,0])

"""Champions statistic"""
# Average performance via indicators
champion_data = game_data.iloc[:,1:].groupby('Champion').mean()

# Probability to be a role
presence = game_data.groupby('Champion')['GameID'].count()
role_prob = game_data.groupby(['Champion','Role'])[['GameID']].count()
role_prob = role_prob.unstack().fillna(0)
for i in range(5):
    role_prob.iloc[:,i] /= presence
role_prob.columns = [x + '_prob' for x in role_prob.columns.levels[1]]
champion_data = pd.concat([champion_data,role_prob], axis=1)

# Win rate in different stages of game
def disretize_time(x):
    if x <= 25: return 'Early'
    elif x > 25 and x <=30: return 'Early-to-middle'
    elif x > 30 and x <=35: return 'Middle'
    elif x > 35 and x <=40: return 'Middle-to-late'
    else: return 'Late'

game_data['Stage'] = game_data['Game time'].map(disretize_time)
stage_win = game_data.groupby(['Champion','Stage','Result'])[['GameID']].count()
stage_total = stage_win.unstack(level=1).groupby('Champion').sum()
stage_win = stage_win.unstack(level=[1,-1]).iloc[:,[1,3,5,7,9]].fillna(0)
stage_win /= stage_total
stage_win.columns = stage_win.columns.levels[1].tolist()
for col in stage_win:
    stage_win[col] = stage_win[col].fillna(stage_win[col].mean())
Late = stage_win['Late']
stage_win = stage_win.drop('Late', axis=1)
stage_win['Late'] = Late
champion_data = pd.concat([champion_data,stage_win], axis=1)

# Filter unusual champions
ftr_champion_data = champion_data.loc[presence[presence > 20].index]

"""Champions similarity"""
ftr_champion_data_corr = ftr_champion_data.T.corr()

def similar_champions(champion, top=5):
    data = pd.DataFrame(ftr_champion_data_corr.loc[champion].sort_values(ascending=False)[1:top+1])
    data.columns=['Similarity']
    return data

# data = similar_champions('Ashe')


"""Team score"""
def team_score(team, plot=False):
    win_rate_team = ftr_champion_data.loc[team].iloc[:,-5:]
    if plot:
        plt.figure(dpi=100)
        plt.plot(win_rate_team.mean(), 'bo-', color='IndianRed')
        plt.ylabel('Team Score')
        plt.xlabel('Game Stage')
        plt.title('Team Score of ' + str(win_rate_team.index.tolist()), y=1.05)
        plt.show()
    return win_rate_team

def scores_comparison(team1, team2, plot=True):
    team1_score = team_score(team1, plot=False)
    team2_score = team_score(team2, plot=False)
    if plot:
        plt.figure(dpi=100)
        plt.plot(team1_score.mean(), 'bo-', color='SkyBlue', label='Team 1')
        plt.plot(team2_score.mean(), 'bo-', color='IndianRed', label='Team 2')
        plt.ylabel('Team Score')
        plt.xlabel('Game Stage')
        plt.title('Comparison of Team Score', y=1.05)
        plt.legend()
        plt.show()
    team1_score.insert(0, column='Team', value=['Team 1' for _ in range(5)])
    team2_score.insert(0, column='Team', value=['Team 2' for _ in range(5)])
    output = pd.concat([team1_score, team2_score])
    output = output.reset_index()
    output = output.set_index(['Team','Champion'])
    return output

# team1 = ['Ornn', 'Olaf', 'LeBlanc', 'Miss Fortune', 'Yuumi']
# team2 = ['Sett', 'Lee Sin', 'Lissandra', 'Aphelios', 'Thresh']
# output = scores_comparison(team1, team2)


"""Detection of counters"""
game_data2 = game_data.set_index('GameID')

def find_counters(champian, top=5):
    loss_gameid = game_data2[(game_data2['Result']==0) & (game_data2['Champion']==champian)].index
    win_gameid = game_data2[(game_data2['Result']==1) & (game_data2['Champion']==champian)].index
    counters = game_data2[game_data2['Result']==1].loc[loss_gameid]
    losers = game_data2[game_data2['Result']==0].loc[win_gameid]
    counters = counters.groupby('Champion')[['Result']].count() # who defeats the given champion
    losers = losers.groupby('Champion')[['Result']].count() # who is defeated by the given champion
    total = counters.merge(losers, how='left', left_index=True, right_index=True).sum(axis=1)
    ftr = total[total > 20].index
    counters /= pd.DataFrame(total, columns=['Result'])
    top_counters = counters.loc[ftr].sort_values(by='Result', ascending=False)[:top]
    top_counters.columns = ['Counter Rate']
    return top_counters

# counters = find_counters('Ashe')

"""Recommender"""
all_teams = game_data['Champion'].values.copy()
all_teams.resize(int(len(all_teams)/5), 5)
all_teams = pd.DataFrame(all_teams,columns=game_data['Role'].unique())
all_teams = all_teams[all_teams.apply(lambda x: len(set(x) & set(ftr_champion_data.index)) == 5, axis=1)]

def recommender(top=False, jun=False, mid=False, adc=False, sup=False, num=1, expect_stage='Middle'):
    dic = {'TOP':top, 'JUNGLE':jun, 'MID':mid, 'ADC':adc, 'SUPPORT':sup}
    if all([x != 0 for x in dic.values()]):
        print('Error: the number of input champions should be less than 5.')
        return
    elif any(dic.values()):
        table = [] # store the most similar champions for each given champion
        roles = [] # store the roles of given champions
        for key, value in dic.items():
            if value:
                similars = similar_champions(value, top=5).index.tolist()
                table.append([value] + similars)
                roles.append(key)
        teams = pd.DataFrame(list(product(*table)), columns=roles) # all possible teams
        teams = teams[teams.apply(lambda x: sum(x.duplicated())==0, axis=1)] # drop if there are duplicated champions in a team
        recmd_teams = pd.merge(all_teams, teams) # find the historical teams
        for col in roles:
            recmd_teams[col] = dic[col]
    else:
        recmd_teams = all_teams.copy()
    # give scores
    col_name = expect_stage + ' Score'
    recmd_teams[col_name] = recmd_teams.apply(lambda x: team_score(x).mean()[[expect_stage]], axis=1)
    recmd_teams = recmd_teams.drop_duplicates()
    return recmd_teams.sort_values(by=col_name, ascending=False)[:num].reset_index(drop=True)

# top=False
# jun=False
# mid=False
# adc=False
# sup=False
# recom_team = recommender(top,jun,mid,adc,sup,num=3,expect_stage='Middle')


"""Merge Recommender"""
def merged_recommender(top=False, jun=False, mid=False, adc=False, sup=False, 
                       num_team=1, num_similar=3, num_counter=1, expect_stage='Middle'):
    team = recommender(top, jun, mid, adc, sup, num_team, expect_stage)
    copy = team.copy()
    copy = copy.set_index(team.columns[-1])
    copy = copy.stack().to_frame()
    copy.columns = ['Champion']

    similar_champs = list(map(lambda x: similar_champions(x,top=num_similar).index.tolist(), copy.iloc[:,0].tolist()))
    similarrate = list(map(lambda x: similar_champions(x,top=num_similar).values.ravel().tolist(), copy.iloc[:,0].tolist()))
    similarrate = [[round(y, 3) for y in x] for x in similarrate]
    copy['Top Similars & Similarity'] =  [list(zip(similar_champs[i],similarrate[i])) for i in range(len(similar_champs))]
    
    counters = list(map(lambda x: find_counters(x,top=num_counter).index.tolist(), copy.iloc[:,0].tolist()))
    counterrate = list(map(lambda x: find_counters(x,top=num_counter).values.ravel().tolist(), copy.iloc[:,0].tolist()))
    counterrate = [[round(y, 3) for y in x] for x in counterrate]
    copy['Top Counters & Counter Rate'] = [list(zip(counters[i],counterrate[i])) for i in range(len(counters))]
    return copy

# merged_recommender(adc='Ashe', sup='Yuumi', num_team=3,num_counter=2, expect_stage='Middle')


if __name__ == '__main__':
    champions = ftr_champion_data.index.tolist()
    print("All champions in the data set...\n")
    print(champions,'\n')
    pd.set_option('max_colwidth', -1)
    print("At least input one champion...")
    top = input("TOP Champion (null if skip): ")
    if len(top) == 0: top = False
    elif top not in champions: 
        raise ValueError("Champion is not available.")
    jun = input("JUNGLE Champion (null if skip): ")
    if len(jun) == 0: jun = False
    elif jun not in champions: 
        raise ValueError("Champion is not available.")
    mid = input("MID Champion (null if skip): ")
    if len(mid) == 0: mid = False
    elif mid not in champions:
         raise ValueError("Champion is not available.")
    adc = input("ADC Champion (null if skip): ")
    if len(adc) == 0: adc = False
    elif adc not in champions: 
        raise ValueError("Champion is not available.")
    sup = input("SUPPORT Champion (null if skip): ")
    if len(sup) == 0: sup = False
    elif sup not in champions: 
        raise ValueError("Champion is not available.")
    num_team = input("The expected number of teams to be recommended (1 if skip): ")
    if len(num_team) == 0: num_team = 1
    num_similar = input("The number of similars (1 if skip): ")
    if len(num_similar) == 0: num_similar = 1
    num_counter = input("The number of counters (1 if skip): ")
    if len(num_counter) == 0: num_counter = 1
    expect_stage = input("The phase (one of Early, Early-to-middle, Middle, Middle-to-late, Late) you concern for win (Middle if skip): ")
    if len(expect_stage) == 0: expect_stage = 'Middle'
    print(merged_recommender(top=top, jun=jun, mid=mid, adc=adc, sup=sup, 
                             num_team=int(num_team), num_similar=int(num_similar), 
                             num_counter=int(num_counter), expect_stage=expect_stage))