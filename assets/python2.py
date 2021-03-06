import argparse
import os
import webbrowser
from multiprocessing.pool import Pool

import pandas as pd
import plotly.graph_objects as go
import time
import tqdm
from itertools import chain, combinations
from sklearn.feature_selection import SelectKBest, f_classif

from server import create_db
from server.db.test_mongo import TestMongo
from server.lookup.faiss import TestModel

STATISTICS = ['average', 'iqr', 'maximum', 'median', 'minimum', 'std_dev']


def get_metric_name(col_label):
    col_label = str(col_label).rstrip("_0123456789")
    for s in STATISTICS:
        suffix = "_" + s
        if col_label.endswith(suffix):
            return col_label[:len(col_label) - len(suffix)]

    return col_label


def powerset(iterable):
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(1, len(s) + 1))


def alles_zusammen(data: pd.DataFrame):
    col_indices = dict()
    for index, column in enumerate(data.columns):
        col_label = str(column).rstrip("_0123456789")
        col_label = col_label.replace('median', 'average').replace('std_dev', 'maximum').replace('acceleration',
                                                                                                 'velocity').replace(
            'minimum', 'maximum')
        if col_label in col_indices:
            col_indices[col_label].append(index)
        else:
            col_indices[col_label] = [index]

    return col_indices


def create_index_combinations(col_indices):
    for combination in powerset(col_indices):
        indices = [col_indices[metric] for metric in combination]
        yield chain(*indices)


def groups_by_stats(data: pd.DataFrame):
    stats_indices = dict()
    for stat in STATISTICS:
        stats_indices[stat] = []

    for index, column in enumerate(data.columns):
        col_label = str(column).rstrip("_0123456789")
        for stat in STATISTICS:
            if col_label.endswith(stat):
                stats_indices[stat].append(index)

    return stats_indices


def groups_by_metrix(data: pd.DataFrame):
    metrix = dict()
    for index, column in enumerate(data.columns):
        metric_name = get_metric_name(str(column))
        if metric_name in metrix:
            metrix[metric_name].append(index)
        else:
            metrix[metric_name] = [index]

    return metrix


def analyze(feature_indices):
    if args.verbose:
        print(f"Process ID: {os.getpid()}\nF: {feature_indices}")
    feature_indices = list(feature_indices)
    df_filtered = df.iloc[:, feature_indices]
    test_df_filtered = test_df.iloc[:, feature_indices]
    model = TestModel()
    model.fit(df_filtered.join(user_ids))
    eval_result, conf_matrix = model.evaluate(test_df_filtered.join(test_user_ids), print_info=args.verbose)
    eval_result["k"] = len(feature_indices)
    eval_result["features"] = list(df_filtered.columns)

    return eval_result


def append_score(s_df, score):
    if s_df is None:
        s_df = pd.DataFrame(columns=list(score))
    return s_df.append(score, ignore_index=True)


parser = argparse.ArgumentParser(description="Run feature selection and store model evaluation in a .csv file.")
parser.add_argument('method', type=str,
                    choices=['k_best', 'brute_force', 'groups_stats', 'groups_metrix', 'alles_zusammen'],
                    metavar='METHOD',
                    help='''feature selection method, choices: {%(choices)s}''')
parser.add_argument('-p', '--processes', type=int, help='Number of processes (default: %(default)s)', default=1)
parser.add_argument('-v', '--verbose', action='store_true')
args = parser.parse_args()

db = create_db(TestMongo())

df = pd.DataFrame(list(db.get_all_metrix()))
test_df = pd.DataFrame(list(db.get_all_metrix_test()))
try:
    df = df.drop("_id", axis="columns")
except KeyError:
    pass
try:
    df = df.drop("session_id", axis="columns")
except KeyError:
    pass
try:
    test_df = test_df.drop("_id", axis="columns")
except KeyError:
    pass
try:
    test_df = test_df.drop("session_id", axis="columns")
except KeyError:
    pass
df = df.dropna()
user_ids = df.pop("user_id")
test_user_ids = test_df.pop("user_id")
k = len(df.columns)
score_df = None
selector = None

pool = Pool(processes=args.processes if args.processes > 0 else 1)


def work(scores, groups):
    for score in tqdm.tqdm(pool.imap_unordered(analyze, create_index_combinations(groups)), total=2 ** len(groups)):
        scores = append_score(scores, score)
    return scores

# Ráno, na obed aj večer, pivo, pivo, pivo, pivo
# Malé, veľké, svetlé, tmavé, pivo, pivo, pivo, pivo
# Muži, ženy, deti, starci, pivo, pivo, pivo, pivo
# Doma, v práci, za volantom, pivo, pivo, pivo, pivo
# Pivo to je zradný nápoj,
# Obsahuje tvrdý náboj, pivo je zákerný nápoj.
# Pivo to je zradný nápoj,
# Obsahuje tvrdý náboj, pivo je zákerný nápoj.
# Ooooooo .
# Na zdravie aj na vracanie, pivo, pivo, pivo, pivo
# Na oslavu aj na žiaľ, pivo, pivo, pivo, pivo
# Za drobné aj za výplatu, pivo, pivo, pivo, pivo
# Na rodinné rozvracanie, pivo, pivo, pivo, pivo
# Pivo to je zradný nápoj,
# Obsahuje tvrdý náboj, pivo je zákerný nápoj.
# Pivo to je zradný nápoj,
# Obsahuje tvrdý náboj, pivo je zákerný nápoj.
# Ooooooo .

if args.method == 'k_best':
    while k > 0:
        selector = SelectKBest(f_classif, k=k)
        selector.fit(df, y=user_ids)
        selected_features = selector.get_support(indices=True)
        score_entry = analyze(selected_features)
        score_df = append_score(score_df, score_entry)
        k = k - 1

    fig = go.Figure()
    for col in score_df.columns[2:]:
        fig.add_scatter(x=score_df["k"], y=score_df[col], name=col)

    try:
        fig.show(renderer="browser")
    except webbrowser.Error:
        print("No runnable browser. Not showing visualisation.")

elif args.method == 'brute_force':
    score_df = work(score_df, range(len(df.columns)))
elif args.method == 'groups_metrix':
    score_df = work(score_df, groups_by_metrix(df))
elif args.method == 'groups_stats':
    score_df = work(score_df, groups_by_stats(df))
elif args.method == 'alles_zusammen':
    score_df = work(score_df, alles_zusammen(data=df))

score_df.to_csv(rf'feature_selection_{args.method}_{time.strftime("%Y%m%d-%H%M%S")}.csv', index=False)