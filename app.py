#!/usr/bin/env python

from __future__ import unicode_literals

from datetime import date, datetime
import json

from flask import Flask
import networkx as nx
import pandas as pd

import vkapi

app = Flask(__name__)


def fetch_graph(va, user_id):
    G = nx.Graph()

    G.add_node(user_id, first_name="me", last_name="me")
    friends = va._do_api_call('friends.get',
                              {'user_id' : user_id,
                               'fields' : 'id,bdate,schools,occupation'})
    for f in friends['items']:
        fid = int(f['id'])
        kwargs = {}
        for k in ['first_name', 'last_name', 'bdate', 'schools', 'occupation']:
            if f.get(k) is not None:
                kwargs[k] = f[k]
        G.add_node(fid, **kwargs)
        G.add_edge(user_id, fid)
    friend_ids = set(G.nodes())
    for fid in list(friend_ids):
        try:
            subfriends = va._do_api_call('friends.get', {'user_id' : fid,
                                                         'fields' : 'id'})
        except vkapi.VkError:
            continue
        for sf in subfriends['items']:
            sfid = int(sf['id'])
            if sfid in friend_ids:
                G.add_edge(fid, sfid)
    return G


def graph_to_df(va, user_id, G):
    def extract_data(G, vkid):
        node = G.node[vkid]
        current_year = datetime.now().year
        row = {}
        if 'bdate' in node:
            date_parts = node['bdate'].split(".")
            if len(date_parts) == 3:
                row['age'] = current_year - int(date_parts[-1])
        if node.get('schools'):
            schools = sorted(node['schools'],
                             key=lambda s: (s.get('year_from')
                                            or -s.get('year_graduated', 0)
                                            or 0))
            row['first_school_city'] = schools[0]['city']
        if 'occupation' in node and node['occupation'].get('type') == 'work':
            row['work'] = node['occupation']['name']
        row['clustering'] = len(set(G.neighbors(user_id))
                                & set(G.neighbors(vkid)))
        return row

    return pd.DataFrame(extract_data(G, vkid) for vkid in G.nodes())


def predict_age(va, df):
    age_known = pd.notnull(df['age'])
    if age_known.sum() > 0:
        age_clustering = df[age_known].clustering / df[age_known].clustering.sum()
        return round((df.age[age_known] * age_clustering).sum())
    else:
        return None


def predict_home_town(va, df):
    city_known = pd.notnull(df['first_school_city'])
    if city_known.sum() > 0:
        counts = df.loc[city_known, ['first_school_city']].apply(pd.value_counts)
        most_probable_city = int(counts.iloc[0].name)
        res = va._do_api_call('database.getCitiesById',
                              {'city_ids' : str(most_probable_city)})
        return res[0]['title']
    else:
        return None


@app.route('/vk-users/<int:user_id>')
def user_info(user_id):
    va = vkapi.VkAPI()
    current_year = datetime.now().year
    profile = va.get_user_profile(user_id)
    bdate_parts = profile.get('bdate', "").split(".")
    if len(bdate_parts) == 3:
        true_age = current_year - int(bdate_parts[-1])
    else:
        true_age = None
    true_home_town = profile.get('home_town')

    G = fetch_graph(va, user_id)
    df = graph_to_df(va, user_id, G)
    predicted_age = predict_age(va, df)
    predicted_home_town = predict_home_town(va, df)

    return json.dumps({'true_home_town': true_home_town,
                       'predicted_home_town': predicted_home_town,
                       'true_age': true_age,
                       'predicted_age': predicted_age})

@app.route("/")
def hello():
    return "Hello World!"

if __name__ == "__main__":
    app.run(debug=True)
