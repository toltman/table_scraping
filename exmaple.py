from table import Table

tab = Table('100tables/tabn' + '105.20' + '.xls', '2019')

print(tab.id)
print(tab.row_info)
# tab.write_xlsx()