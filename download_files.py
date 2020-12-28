import pandas as pd
import requests

df = pd.read_csv('table_list.csv', header=None, names=['tables'])


for tab in df.tables:
    url = 'https://nces.ed.gov/programs/digest/d19/tables/xls/tabn' + tab + '.xls'
    r = requests.get(url)
    open('100tables/tabn' + tab + '.xls', 'wb').write(r.content)