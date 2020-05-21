import difflib
import os
import tkinter as tk
import jinja2
import string
import pandas as pd
import plotly.express as px
import plotly.offline as po
import plotly.graph_objects as graph_objects
from plotly.subplots import make_subplots
from jinja2 import Environment
from tkinter import filedialog
from radon.raw import analyze

TEMPLATE_FOLDER_ABS = 'D:\\Users\\MatusPilnan\\Desktop\\Skola\\ING\\VD\\static\\python\\templates'
TEMPLATE_FOLDER = '\\templates'
TEMPLATE_NAME = 'default.html'

def get_file_lines():
    file_path = filedialog.askopenfilename()
    with open(file_path, encoding='utf-8', mode="r") as f:
        lines = f.readlines()

    return lines


def create_loc_graphs(old, new):
    plots = []
    loc = {'old': analyze("".join(old)), 'new': analyze("".join(new))}
    df = pd.DataFrame([loc['old']]).transpose().reset_index().rename(columns={0: "value", 'index': 'metric'})
    df['file'] = ['old'] * len(df)
    df2 = pd.DataFrame([loc['new']]).transpose().reset_index().rename(columns={0: "value", 'index': 'metric'})
    df2['file'] = ['new'] * len(df2)
    df = df.append(df2)
    fig = px.bar(df, x='metric', y='value', color='file', barmode='group', title='Change of LOC metrics between versions')
    plots.append(po.plot(fig, output_type='div'))

    loc_df = pd.DataFrame([loc['old']]).drop(columns=['loc', 'lloc', 'comments'])
    loc_df2 = pd.DataFrame([loc['new']]).drop(columns=['loc', 'lloc', 'comments'])
    fig2 = make_subplots(rows=1, cols=2, specs=[[{'type':'domain'}, {'type':'domain'}]], subplot_titles=['LOC Metrics in old version', 'LOC Metrics in new version'])
    fig2.add_pie(labels=list(loc_df.columns), values=list(loc_df.iloc[0]), title='Old version', row=1, col=1)
    fig2.add_pie(labels=list(loc_df2.columns), values=list(loc_df2.iloc[0]), title='New version', row=1, col=2)
    fig2.update_traces(hole=.4, hoverinfo="label+percent")
    plots.append(po.plot(fig2, output_type='div'))

    fig = px.bar(df, x='metric', y='value', animation_frame='file', range_y=[0, 1.1 * max(df['value'].max(), df2['value'].max())], title='Change of LOC metrics between versions (animated)')
    plots.append(po.plot(fig, output_type='div'))

    return "".join(plots)


root = tk.Tk()
root.withdraw()

first = get_file_lines()
second = get_file_lines()

differ = difflib.HtmlDiff()
table_html = differ.make_table(first, second)
# with open("out.html", encoding='utf-8', mode="w") as f:
#     f.write(html)


template_env = Environment(loader=jinja2.loaders.FileSystemLoader(TEMPLATE_FOLDER_ABS))
template = template_env.get_template(TEMPLATE_NAME)
template.stream(diff_table_html=table_html, analysis=create_loc_graphs(first, second)).dump("out.html")

os.startfile("out.html")
