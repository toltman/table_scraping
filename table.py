import os
import xlrd
import numpy as np
import pandas as pd
import re

# Table class

class Table():
    ROW_LEVELS = 7
    COL_LEVELS = 7

    def __init__(self, file_directory, year):
        self.filename = file_directory

        # Read Excel workbook
        self.book = xlrd.open_workbook(self.filename, formatting_info=True)
        self.sheet = self.book.sheet_by_index(0)
        self.font = self.book.font_list

        res = re.match(r"Digest (\d{4}).*", self.sheet.name)
        if res:
            self.year = res.group(1)

        self.id = self.get_id()
        self.out_filename = self.get_out_filename()

        self.raw_df = pd.read_excel(self.filename, header=None)

        self.title = self.get_title()
        self.title_lines = self.get_title_lines()
        self.header_lines = self.get_header_lines()

        self.footnotes = self.get_footnotes()

        # Table Column dataframe
        self.col_info = self.parse_col_info()

        # Table Row dataframe
        self.end_row = self.get_row_end()
        self.row_info = self.parse_row_info()
    
        # Table Info dataframe
        self.table_info = self.parse_table_info()

        # Cell info
        self.cell_info = self.parse_cell_info()

        # Add subtables to col_info
        self.add_subtables_to_col()

        # removed
        # adds value_represents to col_info or cell_info
        # self.find_value_represents()
        
        # clean up row_info footnotes
        self.clean_up_rowinfo()

        # gets location values of the table
        # sets table.info.location_in, row_info.location and/or col_info.location_type
        self.find_location()

        # gets the year and adds table_info.year_in
        # sets table.info.year_in, row_info.year and/or col_info.year
        self.find_table_year()

        # drop if all null
        self.drop_if_all_null()

        # clean up multiple whitespace
        self.clean_whitespace()

        # convert all to string
        self.convert_to_string()

        # clean up empty paren
        self.clean_empty_paren()

        # fix multi-cell row_levels
        self.fix_multicell_rows()

        # fix 236.30 jurisdictions
        self.fix_jurisdictions()

        # remove spec char columns
        self.remove_spec_char()

        # add has_SE to the table_info tab
        self.add_has_SE()

        # add column is_total
        # self.add_col_is_total()

        # add standard_error
        self.add_standard_error()

        # add is_dollar
        self.add_is_dollar()

        # add format_string
        self.add_format_string()

        # replace all nan with ""
        self.clean_nan()

        # deals with standard error columns
        # sets table_info.has_SE
        self.find_SE()

        # sets the correct order of columns
        self.order_cols()

        # clean hyphens based on dictionary words
        self.clean_hyphens_dict()



    def clean_hyphens_dict(self):
        """Cleans hyphens out of all tables based on provided dictionary"""

        try:
            hyphen_df = pd.read_csv("scraping_dictionary.csv")
            hyphen_dict = dict(zip(hyphen_df['hyphenated'], hyphen_df['corrected']))

            self.table_info = self.table_info.replace(hyphen_dict, regex=True)
            self.row_info = self.row_info.replace(hyphen_dict, regex=True)
            self.col_info = self.col_info.replace(hyphen_dict, regex=True)
            self.cell_info = self.cell_info.replace(hyphen_dict, regex=True)

        except FileNotFoundError:
            print("scraping_dictionary.csv is missing!")



    def order_cols(self):
        cols = [
            'digest_table_id', 'digest_table_year', 'digest_table_sub_id', 'digest_table_sub_title', 
            'column_index', 'standard_error', 'is_dollar', 'format_string', 'year', 'location', 'location_type', 
            'column_level_1', 'column_level_2', 'column_level_3', 'column_level_4', 'column_level_5', 
            'column_level_6', 'column_level_7', 'column_ref_note_1', 'column_ref_note_2', 'column_ref_note_3', 
            'column_ref_note_4', 'column_ref_note_5', 'column_ref_note_6', 'column_ref_note_7'
            ]
        
        self.col_info = self.col_info[cols]



    def add_col_is_total(self):
        self.col_info.insert(6, 'is_total', 'FALSE')

    def add_standard_error(self):
        self.col_info.insert(6, 'standard_error', 'FALSE')

    def add_is_dollar(self):
        self.col_info.insert(6, 'is_dollar', '')

    def add_format_string(self):
        self.col_info.insert(6, 'format_string', '')


    def add_has_SE(self):
        has_SE = 'FALSE'
        if self.table_info['headnote'].values[0] == '[Standard errors appear in parentheses]':
            has_SE = 'TRUE'
        self.table_info.insert(4, 'has_SE', has_SE)
    
    def remove_spec_char(self):
        pass


    def clean_whitespace(self):
        self.table_info = self.table_info.replace(r"\s+", " ", regex=True)
        self.row_info = self.row_info.replace(r"\s+", " ", regex=True)
        self.col_info = self.col_info.replace(r"\s+", " ", regex=True)
        self.cell_info = self.cell_info.replace(r"\s+", " ", regex=True)

    def clean_nan(self):
        self.table_info = self.table_info.replace("nan", "")
        self.row_info = self.row_info.replace("nan", "")
        self.col_info = self.col_info.replace("nan", "")
        self.cell_info = self.cell_info.replace("nan", "")

    def clean_empty_paren(self):
        self.row_info = self.row_info.replace(r"\(\)", "", regex=True)


    def drop_if_all_null(self):
        self.table_info = self.table_info.dropna(axis=1, how="all")
        self.row_info = self.row_info.dropna(axis=1, how="all")
        self.col_info = self.col_info.dropna(axis=1, how="all")
        # do not remove all blank cell_info rows...this was causing empty tables to not appear
        # self.cell_info = self.cell_info.dropna(axis=1, how="all")

    def convert_to_string(self):
        self.table_info = self.table_info.astype(str)
        self.row_info = self.row_info.astype(str)
        self.col_info = self.col_info.astype(str)
        self.cell_info = self.cell_info.astype(str)


    def clean_up_rowinfo(self):
        self.row_info = self.row_info.replace(r"(.*)\\[0-9]\\", r"\1", regex=True)
        self.row_info = self.row_info.replace(r"(.*)\\[0-9],[0-9]\\", r"\1", regex=True)
        self.row_info = self.row_info.replace(r"(.*)!$", r"\1", regex=True)

    def add_subtables_to_col(self):
        """Adds subtable id and subtable title to col_info dataframe"""
        sub_tables = self.row_info[['digest_table_sub_id', 'digest_table_sub_title']].drop_duplicates()
        
        df_list = []

        for index, row in sub_tables.iterrows():
            df = self.col_info.copy()
            df.insert(2, 'digest_table_sub_id', row['digest_table_sub_id'])
            df.insert(3, 'digest_table_sub_title', row['digest_table_sub_title'])
            df_list.append(df)
        
        self.col_info = pd.concat(df_list)

    def fix_multicell_rows(self):
        # specific table fix, until general solution is needed
        if self.id == "217.15":
            self.row_info.loc[13:18, 'row_level_1'] = 'Framing, floors, foundations--percent of schools with plans'
            self.row_info.loc[63:68, 'row_level_1'] = 'Ventilation/filtration system--percent of schools with plans'
            self.row_info.loc[113:118, 'row_level_1'] = 'Internal communication systems--percent of schools with plans'
            self.row_info['row_level_2'] = self.row_info['row_level_3']
            self.row_info['row_level_3'] = self.row_info['row_level_4']
            self.row_info['row_level_4'] = ''


    def fix_jurisdictions(self):
        # specific fixed, until general solution needed
        if self.id == "236.30":
            self.row_info.loc[70:74, 'row_level_1'] = "Other jurisdictions"
            self.row_info.loc[70:74, 'row_level_2'] = self.row_info.loc[70:74, 'row_level_3']
            self.row_info.loc[70:74, 'row_level_3'] = ''


    def find_value_represents(self):
        """Adds value_represents to col_info and cell_info"""
        
        val_rep = self.col_info.apply(lambda row: self.get_value_represents(row), axis=1)
        self.col_info.insert(5,'value_represents', val_rep)

    def get_value_represents(self, row):
        """Calculate value_represents value given row"""

        title_has_enroll = "enrollment in" in self.title.lower()
        title_has_number = "number" in self.title.lower()
        enroll_or_number = title_has_enroll or title_has_number
        title_has_percent = "percentage" in self.title.lower()
        title_has_expend = "expenditure" in self.title.lower()

        if enroll_or_number and not title_has_percent:
            return "Count"
        elif title_has_percent and not enroll_or_number:
            return "Percentage"
        elif title_has_expend:
            return "Dollar"
        elif "percent" in row['digest_table_sub_title'].lower():
            return "Percentage"
        elif "number" in row['digest_table_sub_title'].lower():
            return "Count"
        elif " per " in row['digest_table_sub_title'].lower():
            return "Rates"
        elif "percent" in row['column_level_1'].lower():
            return "Percentage"
        elif "enrollment" in row['column_level_1'].lower():
            return "Count"
        elif "enroll-ment" in row['column_level_1'].lower():
            return "Count"
        elif "number" in row['column_level_1'].lower():
            return "Count"
        elif "rate" in row['column_level_1'].lower():
            return "Rates"
        elif row['column_level_1'] == "State":
            return "Text"
        elif "number" in row['column_level_2'].lower():
            return "Count"
        elif "ratio" in row['column_level_2'].lower():
            return "Rates"
        elif "percent" in row['column_level_2'].lower():
            return "Percentage"
        return "Not Found"


    def find_location(self):
        """finds and sets location_in, location, and location type"""

        row_location_list = [
            'Region and year',
            'State',
            'Name of district',
            'State or jurisdiction',
        ]

        # identify location by the stubhead
        location_in = ""
        stub_head = self.table_info['stub_head'].values[0]
        if stub_head in row_location_list:
            location_in = "Row"

        self.table_info.insert(4, "location_in", location_in)
        self.table_info.insert(5, "location", "")
        self.table_info.insert(6, "Location_info", "")

        # create location and location_type cols
        self.row_info.insert(20, 'location', "")
        self.row_info.insert(21, 'location_type', "")

        # create location and location_type in col_info table
        self.col_info.insert(6, 'location', "")
        self.col_info.insert(7, 'location_type', "")

        # location variable should be set to lowest level row_level
        if location_in == "Row" and stub_head == "Region and year":
            self.row_info['location'] = self.row_info.apply(self.lowest_level, axis=1)
            self.row_info['location_type'] = "Region"
        elif location_in == "Row":
            self.row_info['location'] = self.row_info.apply(self.lowest_level, axis=1)

            # fixes issue with 'United States' appearing in the is_total row of table
            is_total = self.row_info['is_total'] == 'TRUE'
            self.row_info.loc[is_total, 'location'] = self.row_info.loc[is_total, 'row_level_1']
            self.row_info.loc[is_total, 'row_level_2'] = self.row_info.loc[is_total, 'row_level_1']

            self.row_info['location_type'] =  stub_head
        
        if ~(location_in in ['Row', 'Column']):
            location_in = "Title"
            self.table_info['location_in'] = location_in
            self.table_info['location'] = "United States"
            self.table_info['Location_info'] = ""


    def lowest_level(self, row):
        location = ""
        row_levels = [f"row_level_{x}" for x in range(1,8)]
        for row_level in row_levels:
            if row[row_level] != "":
                location = row[row_level]
        return location


    def find_table_year(self):
        """finds and sets year_in, and year values"""
        # check title for year
        # title ends in YYYY or YYYY-YY
        year1 = re.search(r": (\d{4})$", self.title)
        year2 = re.search(r": (\d{4}–\d{2})$", self.title)
        year3 = re.search(r": (\d{4}-\d{2})$", self.title)

        year = ""
        if year1:
            year = year1.group(1)
        if year2: 
            year = year2.group(1)
        if year3:
            year = year3.group(1)
        
        year_in = ""
        if year1 or year2 or year3:
            year_in = "Title"

        self.table_info.insert(5, 'year_in', year_in)
        self.table_info.insert(6, 'year', year)
        self.row_info.insert(20,'year', '')
        self.col_info.insert(6, 'year', '')

        # finds rows matching year format
        if year_in == "":
            row_list = [f"row_level_{i+1}" for i in range(0, self.ROW_LEVELS)]
            year_col = []

            for index, row in self.row_info.iterrows():
                year_col.append(self.get_year(row[row_list]))
            
            year_series = pd.Series(year_col)
            year_series = year_series.replace('', np.nan)

            if year_series.notnull().any():
                year_in = "Row"
                self.row_info['year'] = year_col
                self.table_info['year_in'] = year_in

        # finds cols matching year format
        if year_in == "":
            col_list = [f"column_level_{i+1}" for i in range(0, self.COL_LEVELS)]
            year_col = []

            for index, row in self.col_info.iterrows():
                year_col.append(self.get_year(row[col_list]))

            year_series = pd.Series(year_col)
            year_series = year_series.replace('', np.nan)

            if year_series.notnull().any():
                year_in = "Column"
                self.col_info['year'] = year_col
                self.table_info['year_in'] = year_in
        
        if year_in == "":
            year_in = "Title"
            self.table_info['year_in'] = year_in

    def get_year(self, series):
        """Helper function to get year matches from a series"""

        year1 = series.str.extract(r".*(\d{4})\s?$")
        year2 = series.str.extract(r".*(\d{4}–\d{2}).*")
        year3 = series.str.extract(r".*(\d{4}-\d{2}).*")
        year4 = series.str.extract(r".*(1999-2000).*")
    
        years_df = pd.concat([year1, year2, year3, year4], axis=1)
        
        years_series = years_df.apply(lambda x: ','.join(x.dropna().astype(str)),axis=1)
        
        return ''.join(years_series)



    def find_SE(self):
        """finds and sets has_SE"""
        pass

    def get_id(self):
        tnum = ""
        res = re.search(r"tabn(\d{3}\.\d{2})\.xls", self.filename)

        if res:
            tnum = res.group(1)

        return tnum


    def get_out_filename(self):
        tab_id = self.id.replace(".", "_")

        return f"output/{self.year}_{tab_id}_activate_step1.xlsx"


    def get_title(self):

        # removing newline characters
        title_cell = self.sheet.cell_value(0,0).replace("\n", "")

        # replace repeated whitespace with a single space
        title_cell = re.sub(" +", " ", title_cell)

        title = ""
        res = re.match(r"Table (\d{3}\.\d{2})\. (.*)", title_cell)

        if res:
            title = res.group(2)
        
        return title


    def get_title_lines(self):
        tlines = 1

        if re.match(r"\[.*\]", self.sheet.cell_value(1,0)):
            tlines = 2

        return tlines


    def AA(self, num, string):
        """Recursively builds column index
        
        Inspired by from this Stackoverflow answer:
        https://stackoverflow.com/a/54837286
        """
        
        r = num % 26
        num = (num - r) // 26
        string = chr(ord("A") + r) + string
        
        if num > 26:
            string = self.AA(num, string)
        elif num > 0:
            string = chr(ord("A") + num - 1) + string
            
        return string
    

    def parse_table_info(self):
        """Returns table_info dataframe"""

        sh = self.sheet
        df = self.raw_df
        tlines = self.title_lines

        # headnote
        headnote = sh.cell_value(1,0) if tlines == 2 else ""

        # stub_head
        stub_head = sh.cell_value(tlines,0)

        # general_note
        general = df[0].str.extract(r"NOTE: (.*)").dropna()
        general_note = general[0].values[0].strip()

        # source
        source = df[0].str.extract(r"SOURCE: (.*)\((.*)\)").dropna()
        source_note = source[0].values[0].strip()

        # last_prepared
        last_prepared = source[1].values[0].strip()

        col_list = [
            'digest_table_id', 
            'digest_table_year', 
            'digest_table_sub_id',
            'digest_table_sub_title',
            'table_title',
            'headnote',
            'stub_head',
            'general_note',
            'source_note',
            'last_prepared'
        ]

        g = self.row_info.groupby([
            'digest_table_sub_id', 
            'digest_table_sub_title'
            ]).size().reset_index()

        tb_info = g[['digest_table_sub_id', 'digest_table_sub_title']]

        tb_info['digest_table_id'] = self.id
        tb_info['digest_table_year'] = self.year
        tb_info['table_title'] = self.title
        tb_info['headnote'] = headnote
        tb_info['stub_head'] = stub_head
        tb_info['general_note'] = general_note
        tb_info['source_note'] = source_note
        tb_info['last_prepared'] = last_prepared

        tb_info = tb_info[col_list]

        return tb_info

    def get_header_lines(self):
        """Returns the index of the last row of the header"""

        for row in range(0,self.sheet.nrows):
            if self.sheet.cell_value(row,0) == 1:
                return row
            
        print("End of file reached, no integer row")
        return 0
    

    # def is_empty(self, series):
    #     """Returns True if row or column is empty"""

    #     if series.isna().all():
    #         return True
    #     else:
    #         return (series.isna() | series.str.match(r"\W")).all()


    # def get_nonempty_cols(self):
    #     cols = [not self.is_empty(self.raw_df.iloc[:, col]) for col in range(0, self.sheet.ncols)]
    #     return list(self.raw_df.loc[:, cols].columns)


    def get_header(self):

        # get list of non-empty columns
        # cols = self.get_nonempty_cols()
        cols = list(range(0,self.sheet.ncols))

        header = pd.read_excel(self.filename,
                                skiprows=self.title_lines,
                                header=None,
                                nrows=self.header_lines - self.title_lines,
                                usecols=cols
                                )

        # drop the first column
        header = header.iloc[:, 1:]

        header = header.ffill(axis=0).ffill(axis=1)
        return pd.MultiIndex.from_arrays(header.values)


    def get_footnotes(self):
        """Returns footnotes dict"""

        df = self.raw_df

        # Extract footnotes from raw df
        footnotes = df[0].str.extract(r"\\([0-9])\\(.*)").dropna().set_index(0)
        return footnotes.to_dict()[1]


    def parse_col_info(self):
        """Returns dataframe with column information"""

        header = self.get_header()
        footnotes_dict = self.get_footnotes()
        
        # remove duplicated column levels
        col_info = header.to_frame(index=False)
        is_duplicate = col_info.apply(lambda row: row.duplicated(), axis=1)
        col_info = col_info.where(~is_duplicate, "")

        # create extra columns for unused columns index levels
        for n in range(col_info.shape[1], self.COL_LEVELS):
            col_info.insert(n, n, "")
        
        # label column levels
        col_info.columns = [f"column_level_{col+1}" for col in col_info.columns]
        
        # add table_id and table_year to col_info
        col_info["digest_table_id"] = self.id
        col_info["digest_table_year"] = self.year

        # # create column_ref_note columns
        # for x in range(0, self.COL_LEVELS):
        #     col = col_info[f"column_level_{x + 1}"].astype(str)

        #     # create a reference column with the footnote number
        #     refs = col.str.extract(r"\\([0-9])\\")

        #     # create new column with the reference note
        #     col_info[f"column_ref_note_{x + 1}"] = refs.replace(footnotes_dict)

        #     # delete footnote from column_level_x
        #     col_level = col.str.replace(r"\\[0-9]\\", "")

        #     col_info[f"column_level_{x + 1}"] = col_level

        for x in range(0, self.COL_LEVELS):
            col = col_info[f"column_level_{x+1}"].astype(str)
            
            # create a reference column with the footnote number
            refs = col.str.extract(r"\\([0-9]),?([0-9])?\\")
            refs = refs.replace(self.footnotes)
            refs = refs.fillna("")
            s = refs[0] + ":::" + refs[1]
            s = s.replace(regex = r":::$", value = "")
            
            # create new column with the reference note
            col_info[f"column_ref_note_{x+1}"] = s
            
            # delete footnote from col_level_x
            new_col = col.str.replace(r"\\([0-9]),?([0-9])?\\", "").str.strip()
            col_info[f"column_level_{x+1}"] = new_col


        # Remove extra headers
        col_info = col_info.fillna("")

        # Drop duplicated rows in header
        col_info = col_info.drop_duplicates().reset_index()

        # create column_index field
        col_info["column_index"] = [self.AA(i,"") for i in col_info.index]

        # list of columns in the desired order
        col_list = [[f"column_level_{x + 1}", f"column_ref_note_{x + 1}"] for x in range(0,7)]
        col_list = list(np.array(col_list).flatten())

        # rearrange column order
        col_info = col_info[
            ['digest_table_id', 'digest_table_year', 'column_index'] + 
            col_list
        ]

        # strip and replace \n
        for col in range(0, col_info.shape[1]):
            new_col = col_info.iloc[:,col].str.strip()
            new_col = new_col.str.replace(r"\.\.+", "", regex=True)
            new_col = new_col.str.replace("/\n", "/")
            new_col = new_col.str.replace("\n", " ")
            new_col = new_col.str.replace("- ", "")
            col_info.iloc[:,col] = new_col

        return col_info

    def get_row_end(self):

        xf_list = self.book.xf_list

        for row in range(self.header_lines + 2, self.sheet.nrows):
            idx = self.sheet.cell_xf_index(row,0)
            top_line_style = xf_list[idx].border.top_line_style
            bottom_line_style = xf_list[idx].border.bottom_line_style

            if top_line_style == 1:
                return row - 1
            elif bottom_line_style == 1:
                return row

        print("Error: No data end row")
        return 0


    def get_leading_spaces(self, string):
        string = str(string)
        res = re.search(r"[^ ]", string)
        
        if res:
            return res.start()
        else:
            return 0
    
    def parse_row_info(self):
        row_level = 0
        indent_level = 0
        rows = self.end_row - self.header_lines
        subtitle = ""
        
        empty = np.empty([rows, self.ROW_LEVELS])
        empty[:] = np.NaN
        
        row_levels = pd.DataFrame(empty,
                                index=range(self.header_lines+1, self.end_row+1))

        for row in range(self.header_lines + 1, self.end_row + 1):
            cell = self.sheet.cell(row, 0)
            cell_xf = self.book.xf_list[cell.xf_index]
            is_bold = bool(self.font[cell_xf.font_index].bold)
            is_empty = bool(cell.value == "")
            indents = self.get_leading_spaces(cell.value)
            is_total = is_bold and (indents == 3 or indents == 5)

            
            if is_empty and self.sheet.cell(row,1).value.strip() != "":
                subtitle = self.sheet.cell(row, 1).value
            
            
            if indents in [0,3,5]:
                indent_level = 0
            else:
                indent_level = indents / 2
            
            
            if is_total:
                row_level = 0
                row_levels.loc[row, "subtitle"] = subtitle
                row_levels.loc[row, "is_total"] = "TRUE"
                row_levels.loc[row, row_level] = cell.value
                row_level = 1
            elif is_bold:
                row_level = 0
                row_levels.loc[row, "subtitle"] = subtitle
                row_levels.loc[row, "is_total"] = "FALSE"
                row_levels.loc[row, row_level] = cell.value
                row_level = 1
            else: 
                row_levels.loc[row, "subtitle"] = subtitle
                row_levels.loc[row, "is_total"] = "FALSE"
                row_levels.loc[row, row_level+indent_level] = cell.value
            
        # forward fill row levels
        row_levels = row_levels.ffill(axis=1).ffill(axis=0)
        is_duplicate = row_levels.apply(lambda row: row.duplicated(), axis=1)
        row_levels = row_levels.where(~is_duplicate, "")

        # rename columns
        row_levels.columns = [f"row_level_{col+1}" for col in range(0,7)] + ["digest_table_sub_title", "is_total"]
        
        # create row_ref_note columns
        for x in range(0, self.ROW_LEVELS):
            col = row_levels[f"row_level_{x+1}"].astype(str)
            
            # create a reference column with the footnote number
            refs = col.str.extract(r"\\([0-9]),?([0-9])?\\")
            refs = refs.replace(self.footnotes)
            refs = refs.fillna("")
            s = refs[0] + ":::" + refs[1]
            s = s.replace(regex = r":::$", value = "")
            
            # create new column with the reference note
            row_levels[f"row_ref_note_{x+1}"] = s
            
            # delete footnote from row_level_x
            new_col = col.str.replace(r"\\([0-9]),?([0-9])?\\", "").str.strip()
            row_levels[f"row_level_{x+1}"] = new_col
        
        row_levels = row_levels.fillna("")

        # generate subtable ids
        subtable_titles = row_levels['digest_table_sub_title'].unique()
        subtable_ids = [self.AA(i, "") for i in range(0, len(subtable_titles))]
        subtable_dict = dict(zip(subtable_titles, subtable_ids))
        row_levels['digest_table_sub_id'] = row_levels['digest_table_sub_title'].replace(subtable_dict)


        # table id and year
        row_levels["digest_table_id"] = self.id
        row_levels["digest_table_year"] = self.year
        
        # list of columns in the desired order
        col_list = [[f"row_level_{x + 1}", f"row_ref_note_{x + 1}"] for x in range(0,7)]
        col_list = list(np.array(col_list).flatten())

        # rearrange column order
        row_levels = row_levels[
            [
                'digest_table_id', 
                'digest_table_year', 
                'digest_table_sub_id',
                'digest_table_sub_title',
            ] + 
            col_list +
            ['is_total']
        ]

        # strip and replace \n
        for col in range(0, row_levels.shape[1]):
            new_col = row_levels.iloc[:,col].str.strip()
            new_col = new_col.str.replace(r"\.\.+", "", regex=True)
            new_col = new_col.str.replace("\n", " ")
            new_col = new_col.str.replace("- ", "")
            row_levels.iloc[:,col] = new_col

        # Clean up footnotes columns
        df_fn = self.raw_df.loc[:, 1:].copy()
        fn_cols = df_fn.apply(lambda x: self.is_fn_col(x), axis=0) 

        for i in fn_cols.index:
            if fn_cols[i]:
                fn_col = df_fn.loc[:, i].fillna("")
                prev_col = df_fn.loc[:, i-1].fillna("").astype(str)
                df_fn.loc[:, i-1] = prev_col + fn_col


        # Clean up special note columns
        sn_cols = df_fn.apply(lambda x: self.is_spec_note_col(x), axis=0) 

        for i in sn_cols.index:
            if sn_cols[i]:
                sn_col = df_fn.loc[:, i].fillna("")
                prev_col = df_fn.loc[:, i-1].fillna("").astype(str)
                df_fn.loc[:, i-1] = prev_col + sn_col
        
        # remove footnote only cols
        df_fn = df_fn.loc[:, ~fn_cols]

        # remove special note only cols
        df_fn = df_fn.loc[:, ~sn_cols]

        # remove empty cols
        df_fn = df_fn.dropna(axis=1, how='all')

        df_fn.columns = range(0, df_fn.shape[1])

        # merge with row data and rename columns
        df = pd.merge(row_levels, df_fn, how='left', left_index=True, right_index=True)
        col_names = list(range(0,df_fn.shape[1]))
        col_names_new = [self.AA(i, "") for i in range(0, df_fn.shape[1])]
        col_names_dict = dict(zip(col_names, col_names_new))
        df = df.rename(columns=col_names_dict)

        # drop row if all NaN in data
        drop_rows = df.loc[:, 'B':].apply(lambda x: self.na_or_empty(x), axis=1)
        df = df[~drop_rows]

        # drop_cols = df.loc[:, 'A':].apply(lambda x: self.na_or_empty(x), axis=0)
        # df = df.loc[:, ~drop_cols]


        # drop row if contains NaN
        # df = df.dropna()

        # create row index
        df.insert(4, 'row_index', np.arange(1,df.shape[0]+1))

        # remove YYYY.0 from years
        df = df.replace(r"^(\d{4})\.0$", r"\1", regex=True)

        return df


    def na_or_empty(self, row):
        is_na = row.isna() 
        is_space = row.astype(str).str.match(r"^\s*$")
        is_empty = (is_na | is_space).all()
        return is_empty
    

    def is_fn_col(self, col):
        """col contains only footnotes"""
        return col.str.match(r"^\\[0-9]\\$").any()

    def is_spec_note_col(self, col):
        """col contains only special notes"""
        return col.str.match(r"!").any()

    
    def parse_cell_info(self):

        data = self.row_info.loc[:, 'A':]

        col_list = [
            'digest_table_id',
            'digest_table_year',
            'digest_table_sub_id',
            'digest_table_sub_title',
            'row_index',
            'column_index',
            'cell_note',
        ]
        cell_info = pd.DataFrame(columns=col_list)

        symbols = ['---', '(---)',  ' ---', ' (---)', '†', '(†)', '#', '(#)', '!', '‡', '*']
        footnotes = ['Not available.',
                    'Not available.',
                    'Not available.',
                    'Not available.',
                    'Not applicable.',
                    'Not applicable.',
                    'Rounds to zero.',
                    'Rounds to zero.',
                    'Interpret data with caution. The coefficient of variation (CV) for this estimate is between 30 and 50 percent.',
                    'Reporting standards not met. Either there are too few cases for a reliable estimate or the coefficient of variation (CV) for this estimate is 50 percent or greater.',
                    'p < .05 significance level.'
                    ]
        symbol_dict = dict(zip(symbols, footnotes))

        for row in data.index:
            for col in data.columns:
                
                cell_val = str(data.loc[row, col])
                
                has_fn = re.match(r".*\\([0-9])\\", cell_val)
                has_multi_fn = re.match(r".*\\([0-9]),([0-9])\\", cell_val)
                is_spec = cell_val in symbols
                has_exclam = re.match(r".*!$", cell_val)
                
                cell_note_1 = ""
                cell_note_2 = ""
                # ref_note = ""
                # spec_note = ""
                
                if has_fn:
                    cell_note_1 = has_fn.group(1)
                if has_multi_fn:
                    cell_note_1 = self.footnotes[has_multi_fn.group(1)]
                    cell_note_2 = self.footnotes[has_multi_fn.group(2)]
                if is_spec:
                    cell_note_1 = symbol_dict[cell_val]
                if has_exclam:
                    cell_note_1 = 'Interpret data with caution. The coefficient of variation (CV) for this estimate is between 30 and 50 percent.'
                if has_fn or is_spec or has_exclam:
                    l = list(self.row_info.loc[row, ['digest_table_id',
                                    'digest_table_year',
                                    'digest_table_sub_id',
                                    'digest_table_sub_title',
                                    'row_index']].values) + [col, cell_note_1]
                    df_row = pd.DataFrame(l, index=col_list).T
                    cell_info = cell_info.append(df_row, ignore_index=True)
                if has_multi_fn:
                    l1 = list(self.row_info.loc[row, ['digest_table_id',
                                    'digest_table_year',
                                    'digest_table_sub_id',
                                    'digest_table_sub_title',
                                    'row_index']].values) + [col, cell_note_1]
                    df_row = pd.DataFrame(l1, index=col_list).T
                    cell_info = cell_info.append(df_row, ignore_index=True)

                    l2 = list(self.row_info.loc[row, ['digest_table_id',
                                    'digest_table_year',
                                    'digest_table_sub_id',
                                    'digest_table_sub_title',
                                    'row_index']].values) + [col, cell_note_2]
                    df_row = pd.DataFrame(l2, index=col_list).T
                    cell_info = cell_info.append(df_row, ignore_index=True)

        
        # replaces single footnote cells
        cell_info['cell_note'] = cell_info['cell_note'].replace(self.footnotes)

        return cell_info


    def write_xlsx(self):
        """Writes to output file"""

        with pd.ExcelWriter(self.out_filename) as writer: #pylint: disable=abstract-class-instantiated
            
            # table info
            table_info = self.table_info.T.reset_index().T

            table_info.to_excel(
                writer, 
                sheet_name="table_info", 
                index=False,
                header=False
            )

            # rows
            row_info = self.row_info.T.reset_index().T

            row_info.to_excel(
                writer,
                sheet_name="row_info",
                index=False,
                header=False
            )

            # reset column headers so they are part of the dataframe
            col_info = self.col_info.T.reset_index().T

            col_info.to_excel(
                writer, 
                sheet_name="column_info",
                index=False,
                header=False
            )

            cell_info = self.cell_info.T.reset_index().T

            cell_info.to_excel(
                writer, 
                sheet_name="cell_info",
                index=False,
                header=False
            )


if __name__ == "__main__":
    directory = "100tables/"
    for filename in os.listdir(directory):
        try: 
            if filename.endswith(".xls"):
                file_directory = os.path.join(directory, filename)
                table = Table(file_directory, "2019")
                print(table.id)
                table.write_xlsx()
        except:
            print('An error occurred')
